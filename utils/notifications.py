"""
Email notifications for Coact requests.

Templates live in assets/notifications/email/ and are named <RequestType>_<Status>_<audience>.<txt|html>.jinja2;
the audience suffix (user/czar/admin) picks the recipients. The .txt template is required and becomes the plain-text
part; a matching .html template, if present, is attached as the HTML alternative. A template may define
{% block subject %} to override the generic subject line.

Kept out of main.py (which connects to MongoDB at import time) so rendering and recipient logic can be unit tested.
"""
import logging
import os
import re
import smtplib
from email.message import EmailMessage
from typing import List, Optional

import jinja2

LOG = logging.getLogger(__name__)

AUDIENCES = ('user', 'czar', 'admin')


def _nonblank(*values) -> Optional[str]:
    """ First value that is a non-empty string after stripping; strawberry UNSET and None are skipped. """
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def pick_fullname(stored: Optional[str], looked_up: Optional[str]) -> Optional[str]:
    """ Name to greet the user with: the one stored in coact, then the directory's, else None (generic greeting). """
    return _nonblank(stored, looked_up)


def status_label(request_status: str) -> str:
    return {'NotActedOn': 'Pending', 'PreApproved': 'Pre-Approved'}.get(request_status, request_status)


def request_type_label(request_type: str) -> str:
    return re.sub(r"(\w)([A-Z])", r"\1 \2", request_type)


def latest_notes(audit, request_notes: Optional[str] = None) -> Optional[str]:
    """
    Notes on the most recent audit entry, i.e. the action this notification is about; reject/complete/incomplete
    store them as "<the request's own notes>\\n<the actor's notes>", so the request's own notes prefix is dropped.
    Older entries are never used: an action without notes must not show an earlier action's notes as its reason.
    """
    if not audit:
        return None
    entry = audit[-1]
    notes = entry.get('notes') if isinstance(entry, dict) else getattr(entry, 'notes', None)
    prefix = (request_notes if isinstance(request_notes, str) else '') + '\n'
    if isinstance(notes, str) and notes.startswith(prefix):
        notes = notes[len(prefix):]
    return _nonblank(notes)


def links() -> dict:
    """ Links for the templates; read per notification so the environment (and tests) can change them. """
    coact_url = os.getenv('COACT_UI_URL', 'https://coact.slac.stanford.edu').rstrip('/')
    docs_url = os.getenv('S3DF_DOCS_URL', 'https://s3df.slac.stanford.edu').rstrip('/')
    return {
        'coact_url': coact_url,
        'requests_url': coact_url + '/requests',
        'profile_url': coact_url + '/myprofile',
        'repos_url': coact_url + '/repos',
        'docs_url': docs_url,
        'access_url': os.getenv('S3DF_ACCESS_URL', docs_url + '/#/access'),
        'help_email': os.getenv('S3DF_HELP_EMAIL', 's3df-help@slac.stanford.edu'),
        'slack_url': os.getenv('S3DF_SLACK_URL', 'https://app.slack.com/client/T1X4J8FJ8/C01965DTG91'),
    }


def notification_context(data: dict, request_type: str, request_status: str, fullname: Optional[str] = None) -> dict:
    """ Variables available to every template: the raw request fields plus normalised names and links. """
    ctx = dict(data)
    fullname = _nonblank(fullname)
    username = _nonblank(data.get('preferredUserName'), data.get('username'))
    eppn = _nonblank(data.get('eppn'))
    ctx.update({
        'request_type': request_type,
        'request_type_label': request_type_label(request_type),
        'status': request_status,
        'status_label': status_label(request_status),
        'fullname': fullname,
        'username': username,
        'eppn': eppn,
        'display_name': fullname or username or eppn or 'an unidentified user',
        'facility': _nonblank(data.get('facilityname')),
        'request_id': str(data['_id']) if data.get('_id') else None,
        'notes': latest_notes(data.get('audit'), data.get('notes')),
    })
    ctx.update(links())
    return ctx


class Email:
    LOG = logging.getLogger(__name__)
    assets_path=None
    template_extension = '.jinja2'
    def __init__(self, server, port, fm='no-reply-s3df-help@slac.stanford.edu', subject_prefix='[Coact] ', assets_path='./assets/notifications/email/'):
        # smtplib.SMTP(host=...) connects eagerly; an Email is created per request, so defer until send()
        self._server = server
        self._port = port
        self._smtp = None
        self.fm = fm
        self.subject_prefix = subject_prefix
        self.assets_path = assets_path
        template_loader = jinja2.FileSystemLoader(searchpath=self.assets_path)
        # names and notes are user supplied, so the html templates must escape them
        self.j2 = jinja2.Environment(
            loader=template_loader,
            autoescape=jinja2.select_autoescape(enabled_extensions=('html.jinja2',), default_for_string=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_file, params):
        t = self.j2.get_template( template_file )
        self.LOG.debug(f"rendering {template_file} with vars {params}")
        return t.render(**params)

    def render_subject(self, template_file, params) -> Optional[str]:
        t = self.j2.get_template( template_file )
        if 'subject' not in t.blocks:
            return None
        subject = ''.join(t.blocks['subject'](t.new_context(params))).strip()
        return ' '.join(subject.split()) or None

    def create(self, to: List[str], subject: str, body: str, cc: List[str] = [], bcc: List[str] = [], html: Optional[str] = None) -> EmailMessage:
        email = EmailMessage()
        email["From"] = self.fm
        email["To"] = ', '.join(to)
        if len(cc):
            email["Cc"] = ', '.join(cc)
        if len(bcc):
            email["Bcc"] = ', '.join(bcc)
        email["Subject"] = self.subject_prefix + subject
        email.set_content(body)
        if html:
            email.add_alternative(html, subtype='html')
        return email

    def send(self, email: EmailMessage) -> bool:
        if self._smtp is None:
            self._smtp = smtplib.SMTP(host=self._server, port=self._port)
        self._smtp.send_message(email)
        return True

    def templates_for(self, template_prefix: str) -> dict:
        """ {audience: {'txt': name, 'html': name or None}} for the templates matching template_prefix. """
        found = {}
        for f in sorted(os.listdir(self.assets_path)):
            if not f.startswith(template_prefix + '_') or not f.endswith(self.template_extension):
                continue
            audience, _, fmt = f[len(template_prefix) + 1:-len(self.template_extension)].partition('.')
            if audience not in AUDIENCES or fmt not in ('txt', 'html'):
                self.LOG.warning(f"ignoring unrecognised notification template {f}")
                continue
            found.setdefault(audience, {'txt': None, 'html': None})[fmt] = f
        for audience, fmts in list(found.items()):
            if not fmts['txt']:
                self.LOG.error(f"notification template for {template_prefix} {audience} has no .txt version; not sending")
                del found[audience]
        return found

    def notify(self, request_type: str, request_status: str, data: dict, template_prefix: str, user: str, czars: List[str] = [], skip_czar_emails = False, admins: List[str] = [ 'sdf-help@slac.stanford.edu', ], dry_run: bool = False, fullname: Optional[str] = None ) -> bool:
        # one request may need to inform multiple parties, so we
        # assume that any templates with the prefix template_prefix should be
        # send to the parties in the template file name's suffix
        templates = self.templates_for(template_prefix)
        self.LOG.info(f"Found templates {templates}")
        params = notification_context(data, request_type, request_status, fullname=fullname)
        for audience, fmts in templates.items():
            to = []
            cc = []
            bcc = []
            email = None
            if audience == 'czar':
                if skip_czar_emails:
                    continue
                to = czars
            elif audience == 'user':
                to = user
                if not skip_czar_emails:
                    cc = czars
            elif audience == 'admin':
                to = admins
            body = self.render( fmts['txt'], params )
            html = self.render( fmts['html'], params ) if fmts['html'] else None

            # format subject line nice
            subject = self.render_subject( fmts['txt'], params ) or f"{request_type_label(request_type)} {status_label(request_status)}"
            email = self.create( to, subject, body, cc=cc, bcc=bcc, html=html )
            LOG.debug(f"sending email from template {fmts['txt']}: {email}")
            if not dry_run:
                self.send( email )
        return False
