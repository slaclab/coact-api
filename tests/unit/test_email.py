"""
Unit tests for request notification emails.

TestPreservesRecipients pins down who is emailed for which event, exactly as before the template rework; those
tests should only change when the recipient rules are changed on purpose. The other classes cover what is new:
the greeting, the html alternative, the subject lines, the notes shown and the links.

main.py is not imported (it connects to MongoDB at import time); Email lives in utils.notifications.
"""
import os

import pytest

from utils.notifications import Email, latest_notes, notification_context, pick_fullname

ASSETS = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'notifications', 'email') + os.sep

USER = 'wilko@slac.stanford.edu'
CZARS = ['czar1@slac.stanford.edu', 'czar2@slac.stanford.edu']
REQUEST = {
    '_id': '6717f0c2a1b2c3d4e5f60718',
    'reqtype': 'UserAccount',
    'preferredUserName': 'wilko',
    'eppn': 'wilko@slac.stanford.edu',
    'facilityname': 'LCLS',
}

# (To, Cc) of every message sent for a UserAccount event, as sent before the template rework
CZARS_HDR = ', '.join(CZARS)
LEGACY_RECIPIENTS = {
    'NotActedOn': [(CZARS_HDR, None), (USER, CZARS_HDR)],
    'PreApproved': [(CZARS_HDR, None), (USER, CZARS_HDR)],
    'Completed': [(CZARS_HDR, None), (USER, CZARS_HDR)],
    'Incomplete': [('sdf-help@slac.stanford.edu', None)],
    'Approved': [],
    'Rejected': [],
}
LEGACY_RECIPIENTS_DONTSENDEMAIL = {
    'NotActedOn': [(USER, None)],
    'PreApproved': [(USER, None)],
    'Completed': [(USER, None)],
    'Incomplete': [('sdf-help@slac.stanford.edu', None)],
    'Approved': [],
    'Rejected': [],
}
NOTIFYING_STATUSES = [s for s, r in LEGACY_RECIPIENTS.items() if r]


@pytest.fixture
def email():
    e = Email('localhost', 25, assets_path=ASSETS)
    e.sent = []
    e.send = lambda msg: e.sent.append(msg) or True
    return e


def notify(email, status, data=REQUEST, user=(USER,), czars=CZARS, **kwargs):
    return email.notify(request_type='UserAccount', request_status=status, data=dict(data),
                        template_prefix=f'UserAccount_{status}', user=list(user), czars=list(czars), **kwargs)


def recipients(email):
    return sorted((m['To'], m['Cc']) for m in email.sent)


def sent_to(email, addr):
    return next(m for m in email.sent if m['To'] == addr)


def text_of(msg):
    return msg.get_body(preferencelist=('plain',)).get_content()


def html_of(msg):
    return msg.get_body(preferencelist=('html',)).get_content()


class TestPreservesRecipients:

    @pytest.mark.parametrize('status', LEGACY_RECIPIENTS)
    def test_preserves_who_is_emailed_for_each_event(self, email, status):
        notify(email, status)
        assert recipients(email) == sorted(LEGACY_RECIPIENTS[status])

    @pytest.mark.parametrize('status', LEGACY_RECIPIENTS_DONTSENDEMAIL)
    def test_preserves_dontsendemail_dropping_all_czar_mail(self, email, status):
        notify(email, status, skip_czar_emails=True)
        assert recipients(email) == sorted(LEGACY_RECIPIENTS_DONTSENDEMAIL[status])

    def test_preserves_rejection_sending_nothing(self, email):
        notify(email, 'Rejected', data=dict(REQUEST, audit=[{'notes': '\nNo sponsor on file'}]))
        assert email.sent == []

    def test_preserves_one_message_per_audience(self, email):
        # each audience now has a .txt and an .html template; they must still make one message, not two
        notify(email, 'Completed')
        assert len(email.sent) == 2

    def test_preserves_sender_and_subject_prefix(self, email):
        notify(email, 'Completed')
        for msg in email.sent:
            assert msg['From'] == 'no-reply-s3df-help@slac.stanford.edu'
            assert msg['Subject'].startswith('[Coact] ')
            assert msg['Bcc'] is None

    def test_preserves_send_failures_propagating(self, email):
        def refuse(msg):
            raise ConnectionRefusedError()
        email.send = refuse
        with pytest.raises(ConnectionRefusedError):
            notify(email, 'Completed')

    def test_preserves_missing_user_address_raising(self, email):
        with pytest.raises(TypeError):
            email.notify(request_type='UserAccount', request_status='Completed', data=dict(REQUEST),
                         template_prefix='UserAccount_Completed', user=None, czars=CZARS)

    def test_preserves_return_value_and_dry_run(self, email):
        assert notify(email, 'Completed', dry_run=True) is False
        assert email.sent == []


class TestFormat:

    @pytest.mark.parametrize('status', NOTIFYING_STATUSES)
    def test_every_message_has_text_then_html(self, email, status):
        notify(email, status)
        for msg in email.sent:
            assert msg.get_content_type() == 'multipart/alternative'
            assert [p.get_content_type() for p in msg.iter_parts()] == ['text/plain', 'text/html']

    @pytest.mark.parametrize('status', NOTIFYING_STATUSES)
    @pytest.mark.parametrize('data', [REQUEST, {'eppn': 'someone@example.org'}, {}], ids=['full', 'eppn-only', 'empty'])
    def test_sparse_requests_render_without_placeholders(self, email, status, data):
        notify(email, status, data=data)
        for msg in email.sent:
            for body in (text_of(msg), html_of(msg)):
                assert 'None' not in body
                assert '{{' not in body and '{%' not in body

    def test_subjects_say_what_and_for_whom(self, email):
        notify(email, 'NotActedOn')
        assert sent_to(email, CZARS_HDR)['Subject'] == '[Coact] Approval needed: S3DF account for wilko (LCLS)'
        assert sent_to(email, USER)['Subject'] == "[Coact] We've received your S3DF account request for LCLS"

    def test_html_escapes_names_and_notes(self, email):
        data = dict(REQUEST, audit=[{'notes': '\n<script>alert(1)</script>'}])
        notify(email, 'Incomplete', data=data, fullname='<b>Mallory</b>')
        html = html_of(email.sent[0])
        assert '<script>' not in html and '&lt;script&gt;' in html
        assert '<b>Mallory</b>' not in html and '&lt;b&gt;Mallory&lt;/b&gt;' in html
        # plain text is not html, so it carries the values verbatim
        assert '<script>alert(1)</script>' in text_of(email.sent[0])


class TestGreeting:

    def test_user_greeted_by_full_name(self, email):
        notify(email, 'Completed', fullname='Wilko Kroeger')
        msg = sent_to(email, USER)
        assert text_of(msg).startswith('Hi Wilko Kroeger,')
        assert 'Hi Wilko Kroeger,' in html_of(msg)

    @pytest.mark.parametrize('fullname', [None, '', '   '])
    def test_blank_name_gets_a_generic_greeting(self, email, fullname):
        notify(email, 'Completed', fullname=fullname)
        assert text_of(sent_to(email, USER)).startswith('Hello,')

    def test_czar_email_names_the_user(self, email):
        notify(email, 'NotActedOn', fullname='Wilko Kroeger')
        text = text_of(sent_to(email, CZARS_HDR))
        assert text.startswith('Hello LCLS czars,')
        assert 'There is a new S3DF account request in LCLS from Wilko Kroeger.' in text

    def test_czar_email_falls_back_to_username(self, email):
        notify(email, 'NotActedOn')
        assert 'request in LCLS from wilko.' in text_of(sent_to(email, CZARS_HDR))

    @pytest.mark.parametrize('stored, looked_up, expected', [
        ('Wilko Kroeger', 'W. Kroeger', 'Wilko Kroeger'),   # coact's stored name wins
        ('', 'W. Kroeger', 'W. Kroeger'),                   # blank stored name falls back to the directory
        (None, ' W. Kroeger ', 'W. Kroeger'),
        (None, None, None),
        ('  ', '', None),
    ])
    def test_name_precedence(self, stored, looked_up, expected):
        assert pick_fullname(stored, looked_up) == expected


class TestNotes:

    def test_admin_failure_email_shows_the_error(self, email):
        data = dict(REQUEST, audit=[{'notes': '\nRequest x did not complete: LDAP timeout'}])
        notify(email, 'Incomplete', data=data)
        assert '> Request x did not complete: LDAP timeout' in text_of(email.sent[0])

    def test_requests_own_notes_are_not_shown_as_the_error(self, email):
        data = dict(REQUEST, notes='I am a postdoc', audit=[{'notes': 'I am a postdoc\nLDAP timeout'}])
        notify(email, 'Incomplete', data=data)
        text = text_of(email.sent[0])
        assert '> LDAP timeout' in text and 'postdoc' not in text

    def test_an_earlier_actions_notes_are_not_shown_as_the_error(self, email):
        # e.g. a facility change, then a failure recorded without notes
        data = dict(REQUEST, audit=[{'notes': 'Changed facility from A to LCLS'}, {'notes': '\n'}])
        notify(email, 'Incomplete', data=data)
        text = text_of(email.sent[0])
        assert 'Error:' not in text and 'Changed facility' not in text

    @pytest.mark.parametrize('audit, expected', [
        ([{'notes': '\nfirst'}, {'notes': '\nsecond'}], 'second'),
        ([{'notes': '\nfirst'}, {'actedby': 'czar'}], None),
        ([], None),
        (None, None),
    ])
    def test_only_the_newest_audit_entry_counts(self, audit, expected):
        assert latest_notes(audit) == expected


class TestLinks:

    def test_links_default_to_production(self, email, monkeypatch):
        monkeypatch.delenv('COACT_UI_URL', raising=False)
        notify(email, 'NotActedOn')
        assert 'https://coact.slac.stanford.edu/requests' in text_of(sent_to(email, CZARS_HDR))

    def test_links_follow_coact_ui_url(self, email, monkeypatch):
        monkeypatch.setenv('COACT_UI_URL', 'https://coact-dev.slac.stanford.edu/')
        notify(email, 'NotActedOn')
        msg = sent_to(email, CZARS_HDR)
        assert 'https://coact-dev.slac.stanford.edu/requests' in text_of(msg)
        assert 'href="https://coact-dev.slac.stanford.edu/requests"' in html_of(msg)
        assert 'coact.slac.stanford.edu' not in text_of(msg)

    def test_context_reads_the_environment_per_call(self, monkeypatch):
        monkeypatch.setenv('COACT_UI_URL', 'http://localhost:3000')
        assert notification_context(REQUEST, 'UserAccount', 'NotActedOn')['coact_url'] == 'http://localhost:3000'
