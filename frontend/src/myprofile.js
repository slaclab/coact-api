import React, { Component, useState, useEffect } from "react";
import { useQuery, useMutation, gql } from "@apollo/client";
import { NavLink } from "react-router-dom";
import _ from "lodash";
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Card from "react-bootstrap/Card";
import Modal from 'react-bootstrap/Modal';
import Form from 'react-bootstrap/Form';
import Table from 'react-bootstrap/Table';
import Alert from 'react-bootstrap/Alert';
import InputGroup from 'react-bootstrap/InputGroup';
import ListGroup from 'react-bootstrap/ListGroup';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faXmark, faPlus, faRefresh, faUpload } from '@fortawesome/free-solid-svg-icons'
import { DateTimeDisp, TwoPrecFloat, YesNo } from './tabs/widgets'

const HOMEDETAILS = gql`
query {
  whoami {
    Id
    username
    fullname
    uidnumber
    eppns
    preferredemail
    shell
    publichtml
    isAdmin
    groups
    earliestCompletedUserAccountRegistration
    storages {
      Id
      purpose
      gigabytes
      storagename
      rootfolder
      usage {
        gigabytes
      }
    }
  }
}
`;

const CHANGE_USER_SHELL_MUTATION = gql`
mutation requestUserChangeShell($request: CoactRequestInput!){
  requestUserChangeShell(request: $request){
    username
    shell
  }
}
`;

const CHANGE_PUBLIC_HTML_MUTATION = gql`
mutation requestUserPublicHtml($request: CoactRequestInput!){
  requestUserPublicHtml(request: $request){
    username
    publichtml
  }
}
`;


const USER_UPDATE_EPPN_MUTATION = gql`
mutation userUpdateEppn($eppns: [String!]!){
  userUpdateEppn(eppns: $eppns){
    username
    shell
    eppns
  }
}
`;

const USER_UPDATE_USER = gql`
mutation userUpdate($user: UserInput!){
  userUpdate(user: $user){
    username
    shell
    eppns
    preferredemail
  }
}
`;

const QUOTA_REQUEST = gql`
mutation requestUserQuota($request: CoactRequestInput!){
  requestUserQuota(request: $request){
    Id
  }
}
`;

const SSHKeysService = process.env.REACT_APP_SLAC_MFA_SSH_KEYS_SERVER;

function SSHKeysComponent(props) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [upModal, setUpModal] = useState(false);
  const [ref, setref] = useState(0); // Use this to force a refresh
  const user = props.username;

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(SSHKeysService + "/api/list/"+user);
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const result = await response.json();
        setData(result);
      } catch (error) {
        setError(error);
      }
    }

    fetchData();
  }, [ref]); // Empty dependency array means this runs once on mount

  if (error) return <div>Error: {error.message}</div>;
  if (!data) return <div>Loading...</div>;

  console.log(data);

  const refreshSSHKey = async function(fingerprint) {
    console.log("Need to refresh fingerprint", fingerprint);
    const response = await fetch(SSHKeysService + "refresh/"+user+"/"+fingerprint, {method: "PATCH"});
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const result = await response.json();
    console.log(result);
    setref((ref) => ref + 1);
  }

  const inactivateSSHKey = async function(fingerprint) {
    console.log("Inactivating fingerprint", fingerprint);
    const response = await fetch(SSHKeysService + "inactivate/"+user+"/"+fingerprint, {method: "DELETE"});
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const result = await response.text();
    console.log(result);
    setref((ref) => ref + 1);
  }

  const showSSHKeyUploadModal = function() {
    setUpModal(true);
  }

  const closeSSHKeyModal = function() { 
    setUpModal(false);
    setref((ref) => ref + 1);    
  }

  return (<div>
    <div className="sshkey header">
      <span className="fp">Fingerprint</span>
      <span className="ac">Is Active</span>
      <span className="ca">Created At</span>
      <span className="vu">Valid Until</span>
      <span className="ea">Expires At</span>
      <span className="actions">
        <Button variant="secondary" className="mx-1" onClick={showSSHKeyUploadModal} ><FontAwesomeIcon icon={faPlus} title="Upload a new SSH public key"/></Button>
      </span>
    </div>{_.map(data, (sk) => (
    <div key={sk["finger_print"]} className="sshkey">
      <span className="fp">{sk["finger_print"]}</span>
      <span className="ac"><YesNo value={sk["is_active"]}/></span>
      <span className="ca"><DateTimeDisp value={sk["created_at"]}/></span>
      <span className="vu"><DateTimeDisp value={sk["valid_until"]}/></span>
      <span className="ea"><DateTimeDisp value={sk["expires_at"]}/></span>
      <span className="actions">
        <Button variant="secondary" className="mx-1" onClick={() => refreshSSHKey(sk["finger_print"])} title="Renew the SSH public key for another 24 hours"><FontAwesomeIcon icon={faRefresh}/></Button>
        <Button variant="secondary" className="mx-1" onClick={() => inactivateSSHKey(sk["finger_print"])} title="Invalide this SSH public key"><FontAwesomeIcon icon={faXmark}/></Button>
      </span>
    </div>
    ))}
    <UploadSSHKeyModal show={upModal} closeModal={closeSSHKeyModal} username={user}/>
    </div>);
}


class UploadSSHKeyModal extends Component {
  constructor(props) {
    super(props);
    this.state = {isInvalid: false, validationMsg: "", pubkey: ""}
    this.uploadPublicKey = () => {
      if(_.isNil(this.state.pubkey) || this.state.pubkey.length <=0) {
        this.setState({isInvalid: true, validationMsg: "Please enter a valid SSH public key"});
        return;
      }
      const processResponse = async (resp) => { 
        if(resp.ok) {
          return resp.json()
        } else {
          const respdata = await resp.text(); 
          return Promise.reject(new Error(resp.statusText + " --> " + respdata));
        }
      }
      fetch(SSHKeysService + "upload/"+this.props.username, {
        method: "POST", 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: this.props.username, public_key: this.state.pubkey })
      })
      .then((resp) => { return processResponse(resp) })
      .then((status) => { props.closeModal() })
      .catch((err) => { this.setState({isInvalid: true, validationMsg: err.message})})
    }
    this.handleClose = function() { 
      props.closeModal();
    }
  }
  render() {
    const placeholder = `---- BEGIN SSH2 PUBLIC KEY ----
Comment: "256-bit ED25519, converted by user@mylaptop from OpenSSH"
AAAAC3NzaC1lZDI1NTE5AAAAIG+FlqJttIGCNqIewiBPCCTCN2EACKMs8uOCaTlPOY5q
---- END SSH2 PUBLIC KEY ----`;
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose} className="sshkeymodal" size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Upload SSH Public key</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="instructions">
            <p>This page provides instructions for generating a new SSH keypair for use with S3DF. Specifically, we present shell commands that you should paste into your local (eg laptop) terminal that will create a SSH private and public keypair. You will then be able to utilize this keypair to SSH into S3DF without having to always enter a username, password and 2factor (duo).</p>
            <p>Our implementation also considers the use of time limited SSH keys, so the generated keypair that is only valid for a limited time period. This is currently set to a maximum of 7 days. For further security, you will also need to refresh' your keys at least every 25 hours for the keypair to be valid.</p>
            <p>You may generate as may keypairs as you like and on as many computers as you like. However, you must register each public key with our service before you can use it to access S3DF.</p>
            <p>To create a new private key, please use the enter commands on the computer terminal:</p>
            <ListGroup className="codeinstructions">
              <ListGroup.Item>
                <div className="comment">Setup the local directories for the keypairs</div>
                <code>mkdir -p ~/.ssh/s3df && chmod 700 ~/.ssh/s3df</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Generate a new keypair</div>
                <code>ssh-keygen -t ed25519 -f ~/.ssh/s3df/temp-key -C "{this.props.username}"</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Determine the SHA256 fingerprint and move the key to the correct location</div>
                <code>fingerprint=$(ssh-keygen -lf ~/.ssh/s3df/temp-key | cut -f2 -d' ' | sed 's|[/+]|.|g')</code>
                <code>mv ~/.ssh/s3df/temp-key ~/.ssh/s3df/&#36;&#123;fingerprint&#125;</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Perhaps just delete this?</div>
                <code>mv ~/.ssh/s3df/temp-key.pub ~/.ssh/s3df/&#36;&#123;fingerprint&#125;.pub</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Remove any old keypairs that are probably expired</div>
                <code>find ~/.ssh/s3df -type f -name 'SHA256:*' ! -name '*.pub' -print0 -atime +14 # -delete</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Configure your local ssh configuration to include the s3df config</div>
                <code>grep -q "Include ~/.ssh/s3df/s3df.conf" ~/.ssh/config || sed -i '1s@^@Include ~/.ssh/s3df/s3df.conf\n\n@' ~/.ssh/config</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Add s3df ssh dropin config to utilize the private key when ssh'ing into S3DF</div>
                <code>cat &gt; ~/.ssh/s3df/s3df.conf &lt;&lt; EOF</code>
                <code>Host sdfssh001 sdfssh001.slac.stanford.edu sdfssh001.sdf.slac.stanford.edu sdfssh002 sdfssh002.slac.stanford.edu sdfssh002.sdf.slac.stanford.edu s3dflogin-mfa.slac.stanford.edu
&#36;(find ~/.ssh/s3df -type f -name 'SHA256:*' ! -name '*.pub' -print0 | xargs -0 -n1 echo '    IdentityFile ')</code>
                <code>EOF</code>
              </ListGroup.Item>
              <ListGroup.Item>
                <div className="comment">Determine the public key for your newly minted keypair - this must be uploaded to our servers so that you can use this keypair to access S3DF</div>
                <code>ssh-keygen -e -f ~/.ssh/s3df/&#36;&#123;fingerprint&#125;</code>
              </ListGroup.Item>
            </ListGroup>
            <p>The output from the previous set of commands provides the ssh public key that we can use to identify you on our servers when you use the associated private key to ssh into our systems.</p>
            <p>Please enter this public key into the following form so that it may be registered.</p>
            <Form noValidate>
              <Form.Group className="mb-3">
                <Form.Label>Upload your SSH public key</Form.Label>
                <Form.Control as="textarea" rows={5} placeholder={placeholder} isInvalid={this.state.isInvalid} onChange={(ev) => this.setState({isInvalid: false, validationMsg: "", pubkey: ev.target.value})}/>
                <Form.Control.Feedback type="invalid">{this.state.validationMsg}</Form.Control.Feedback>
              </Form.Group>
            </Form>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.uploadPublicKey}>
            Upload
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}


class ChangePreferredEmail extends Component {
  constructor(props) {
    super(props);
    this.state = { preferredemail: props.userdetails.preferredemail, preferredemailInvalid: false }
    this.handleClose = () => { this.props.setShow(false); }
    this.setPreferredEmail = (event) => { this.setState({ preferredemail: event.target.value }) }
    this.changePreferredEmail = () => {
      console.log(this.state.preferredemail);
      if(_.isEmpty(this.state.preferredemail)) {
        this.setState({ preferredemailInvalid: true });
        return;
      }
      const emailre = /^(([^<>()[\]\.,;:\s@\"]+(\.[^<>()[\]\.,;:\s@\"]+)*)|(\".+\"))@(([^<>()[\]\.,;:\s@\"]+\.)+[^<>()[\]\.,;:\s@\"]{2,})$/i;
      if(!String(this.state.preferredemail).toLowerCase().match(emailre)) {
        this.setState({ preferredemailInvalid: true});
        return;
      }

      this.props.changePreferredEmail(this.state.preferredemail);
      this.props.setShow(false);
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Preferred email for {this.props.userdetails.username}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="mb-3">
            <Form.Text>Please enter an preferred email address that we can use to contact you</Form.Text>
            <InputGroup hasValidation>
              <Form.Control type="text" value={this.state.preferredemail} placeholder="Please enter a valid email address" onChange={this.setPreferredEmail} isInvalid={this.state.preferredemailInvalid}/>
              <Form.Control.Feedback type="invalid">Please enter a valid email address</Form.Control.Feedback>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.changePreferredEmail}>
            Change Preferred Email
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class ChangeUserShell extends Component {
  constructor(props) {
    super(props);
    this.state = { shell: props.userdetails.shell, shellInvalid: false }
    this.handleClose = () => { this.props.setShow(false); }
    this.userChangeShell = () => {
      console.log(this.state.shell);
      if(_.isEmpty(this.state.shell)) {
        this.setState({ shellInvalid: true });
        return;
      }
      this.props.userChangeShell(this.state.shell);
      this.props.setShow(false);
    }
    this.setShell = (event) => { this.setState({ shell: event.target.value }) }
    this.supportedShells = [
      "/bin/bash",
      "/bin/tcsh",
      "/bin/zsh"
    ]
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Change shell for {this.props.userdetails.username}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="mb-3">
            <InputGroup hasValidation>
              <Form.Select name="shell" value={this.state.shell} onChange={this.setShell}  isInvalid={this.state.shellInvalid}>
                <option value="">Please choose a shell</option>
                { _.map(this.supportedShells, (s) => { return (<option key={s} value={s}>{s}</option>)}) }
              </Form.Select>
              <Form.Control.Feedback type="invalid">Please choose a valid shell.</Form.Control.Feedback>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.userChangeShell}>
            Change Shell
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class AddRemoveEPPNs extends Component {
  constructor(props) {
    super(props);
    this.state = { eppns: props.userdetails.eppns, newEPPN: "", newEPPNInvalid: false, newEPPNInvalidMessage: "", moreThanOneEPPN: props.userdetails.eppns.length > 1, serversideerror: false, serversideerrormsg: "" }
    this.handleClose = () => { this.props.setShow(false); }

    this.setNewEppn = (event) => { this.setState({ newEPPN: event.target.value})}
    this.updateEPPNs = () => {
      this.setState({ serversideerror: false, serversideerrormsg: "" });
      if(_.isEmpty(_.xor(this.state.eppns, this.props.eppns))) {
        console.log("No changes to EPPNs");
        return;
      }
      this.props.updateEppns(this.state.eppns, (errormsg) => this.setState({ eppns: props.userdetails.eppns, serversideerror: true, serversideerrormsg: "" + errormsg}));
    }
    this.addNewEPPN = (event) => {
      this.setState({ newEPPNInvalid: false,  newEPPNInvalidMessage: ""});
      if(_.isEmpty(this.state.newEPPN)) {
        this.setState({ newEPPNInvalid: true,  newEPPNInvalidMessage: "An EPPN cannot be empty"});
        return;
      }
      const emailre = /^(([^<>()[\]\.,;:\s@\"]+(\.[^<>()[\]\.,;:\s@\"]+)*)|(\".+\"))@(([^<>()[\]\.,;:\s@\"]+\.)+[^<>()[\]\.,;:\s@\"]{2,})$/i;
      if(!String(this.state.newEPPN).toLowerCase().match(emailre)) {
        this.setState({ newEPPNInvalid: true,  newEPPNInvalidMessage: "Please use a valid EPPN. For example, userid@institution.org"});
        return;
      }
      if(_.includes(this.state.eppns, this.state.newEPPN)) {
        this.setState({ newEPPNInvalid: true,  newEPPNInvalidMessage: this.state.newEPPN + " is already being used"});
        return;
      }
      const updatedEppns = _.concat(this.state.eppns, [this.state.newEPPN])
      this.setState({eppns: updatedEppns, newEPPN: "", moreThanOneEPPN: updatedEppns.length > 1}, () => { this.updateEPPNs(); });
    }
    this.removeEppn = (eppn) => {
      let updatedEppns = _.without(this.state.eppns, eppn);
      if(_.isEmpty(updatedEppns)) {
        console.log("Can't have an empty EPPN list"); // We really should not be here
        return;
      }
      this.setState({ eppns: updatedEppns, moreThanOneEPPN: updatedEppns.length > 1 }, () => { this.updateEPPNs(); });
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Add remove EPPN's for {this.props.userdetails.username}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert show={this.state.serversideerror}>{this.state.serversideerrormsg}</Alert>
          <Table bordered>
            <tbody>
              { _.map(this.state.eppns, (e) => { return (<tr key={e}><td>{e}</td><td><Button className={this.state.moreThanOneEPPN ? "" : "d-none"} size="sm" onClick={() => this.removeEppn(e)}><FontAwesomeIcon icon={faXmark}/></Button></td></tr>) }) }
            </tbody>
          </Table>
          <Form.Label type="text">To add a new EPPN, please use the box below</Form.Label>
          <InputGroup hasValidation>
            <Form.Control type="text" placeholder="Enter new EPPN userid@institution.org" value={this.state.newEPPN} onChange={this.setNewEppn} isInvalid={this.state.newEPPNInvalid}/>
            <Button size="sm" onClick={this.addNewEPPN}><FontAwesomeIcon icon={faPlus}/></Button>
            <Form.Control.Feedback type="invalid">{this.state.newEPPNInvalidMessage}</Form.Control.Feedback>
          </InputGroup>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class StorageQuotaRequest extends Component {
  constructor(props) {
    super(props);
    this.state = { gigabytes: props.storage.gigabytes, notes: "", gigabytesinvalid: false
    }
    this.handleClose = () => { this.props.setShow(false); }
    this.setgigabytes = (event) => { this.setState({ gigabytes: _.toNumber(event.target.value) }) }
    this.setnotes = (event) => { this.setState({ notes: event.target.value }) }

    this.quotaRequest = () => {
      console.log(this.state);
      this.props.requestQuota(this.props.storage.storagename, this.state.gigabytes, this.props.storage.purpose, this.state.notes);
      this.props.setShow(false);
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Quota request for {this.props.userdetails.username}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form.Text>Request a change in quota on volume {this.props.storage.storagename} used for {this.props.storage.purpose}. <br/> You currently have {this.state.gigabytes} GB</Form.Text>
          <Row className="mb-3">
            <InputGroup hasValidation>
              <Form.Control className="my-2" type="text" value={this.state.gigabytes} placeholder="Please enter the storage requested in GB" onChange={this.setgigabytes} isInvalid={this.state.gigabytesinvalid}/>
              <InputGroup.Text className="my-2">GB</InputGroup.Text>
              <Form.Control.Feedback type="invalid">Please enter a valid gigabytes</Form.Control.Feedback>
            </InputGroup>
          </Row>
          <Row className="mb-3">
            <InputGroup>
              <Form.Control as="textarea" rows={3} value={this.state.notes} placeholder="Please enter any additional comments" onChange={this.setnotes}/>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.quotaRequest}>
            Request a change
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class UserStorage extends Component {
  constructor(props) {
    super(props);
    this.state = { showModal: false }
    this.setShowModal = (show) => { this.setState({ showModal: show }) }
  }

  render() {
    return (
      <>
      <Row><Card.Subtitle title={this.props.storage.rootfolder}>{this.props.storage.purpose}</Card.Subtitle><hr/></Row>
      <Row>
        <Col>
          <Row className="mx-2">Quota: {this.props.storage.gigabytes} GB</Row>
        </Col>
        <Col md={3}>
          <Button disabled={true} className="my-2" variant="secondary" onClick={() => this.setState({showModal: true})}>Request more</Button>
        </Col>
      </Row>
      <StorageQuotaRequest show={this.state.showModal} setShow={this.setShowModal} userdetails={this.props.userdetails} storage={this.props.storage} requestQuota={this.props.requestQuota} />
      </>
    )
  }
}


class RequestPublicHTML extends Component {
  constructor(props) {
    super(props);
    this.state = { agreedToConditions: false, showErr: false, errorMsg: "" }
    this.handleClose = () => { this.props.setShow(false); }
    this.agreeToConditions = (event) => { console.log(event.target.checked); this.setState({ agreedToConditions: event.target.checked, showErr: false  }) }
    this.enablePublicHTML = () => {
      console.log(this.state.agreedToConditions);
      if(!this.state.agreedToConditions) {
        this.setState({ showErr: true, errorMsg: "Please agree to the terms and conditions to turn on your public HTML space." });
        return;
      }

      this.props.userChangePublicHtml(true, () => {this.props.setShow(false)}, (errorMessage) => { this.setState({showErr: true, errorMsg: errorMessage})});
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Enable public HTML for {this.props.userdetails.username}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="mb-3">
            <div><p>Publicly accessible content hosted in S3DF is subject to the <a href="https://www2.slac.stanford.edu/comp/slacwide/account/IT-057-Acceptable-Use-of-Information-Technology-Resources.pdf" target="_blank">SLAC Acceptable Use of Information Technology Resources Policy</a>.</p>
            <p>For more details, please see the <a href="https://s3df.slac.stanford.edu/public/doc/#/service-compute?id=s3df-static-sites" target="_blank">S3DF documentation</a>.</p>
            </div>
            <InputGroup className="mt-3" hasValidation>
              <InputGroup.Text>I agree to these terms and conditions</InputGroup.Text>
              <InputGroup.Checkbox value={this.state.agreedToConditions} onChange={this.agreeToConditions} isInvalid={this.state.showErr} />
              <Alert show={this.state.showErr}>{this.state.errorMsg}</Alert>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.enablePublicHTML}>
            Enable public HTML
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}


class UserDetails extends Component {
  constructor(props) {
    super(props);
    this.showUserShellModal = function() { props.setChgShellShow(true) }
    this.showEppnModal = function() { props.setUpdtEppnShow(true) }
    this.showPrefEmailModal = function() { props.setUpdtPrefEmail(true) }
    this.showPublicHTML = function() { props.setEnblPublicHtml(true) }
    this.publichtmlurl = "https://s3df.slac.stanford.edu/people/" + props.userdetails.username;
    this.publichtmlfolder = _.find(this.props.userdetails.storages, ["purpose", "home"]) ? _.find(this.props.userdetails.storages, ["purpose", "home"])["rootfolder"] + "/public_html" : "<home>/public_html";
  }
  render() {
    return (
      <>
      <Container fluid id="myprofile">
        <Row>
          <Col>
            <Card>
              <Card.Header>Account</Card.Header>
              <Card.Body>
                <Row className="my-1"><Col md={3}><span className="tbllbl">Userid</span></Col><Col>{this.props.userdetails.username}</Col></Row>
                <Row className="my-1"><Col md={3}><span className="tbllbl">UID</span></Col><Col>{this.props.userdetails.uidnumber}</Col></Row>
                <Row className="my-1"><Col md={3}><span className="tbllbl">Name</span></Col><Col>{this.props.userdetails.fullname}</Col></Row>
                <Row className="my-1"><Col md={3}><span className="tbllbl">User as of</span></Col><Col><DateTimeDisp value={this.props.userdetails.earliestCompletedUserAccountRegistration}/></Col></Row>
                
                <hr/>
                <Row><Col md={3}><span className="tbllbl">Shell</span></Col><Col md={5}>{this.props.userdetails.shell}</Col><Col><Button disabled={false} variant="secondary" onClick={this.showUserShellModal}>Change my shell</Button></Col></Row>
                <hr/>
                <Col>
                  <Row><Card.Subtitle>EPPNs</Card.Subtitle></Row>

                  <Row><Col md={8}><ul className="ps-5">
                  {
                    _.map(this.props.userdetails.eppns, (e) => { return (<li key={e}>{e}</li>) })
                  }
                  </ul></Col><Col><Button className="d-none" variant="secondary" onClick={this.showEppnModal} >Add/remove EPPNs</Button></Col>
                  </Row>
                </Col>
                <hr/>
                <Row><Card.Subtitle>Group memberships</Card.Subtitle><ul className="ps-5">
                {
                  _.map(this.props.userdetails.groups, (e) => { return (<li key={e}>{e}</li>) })
                }
                </ul></Row>
              </Card.Body>
            </Card>
          </Col>
          <Col className="me-2">
            <Row>
              <Card className="px-0">
                <Card.Header>Storage</Card.Header>
                <Card.Body>
                {
                  _.map(this.props.userdetails.storages, (s) => { return (<UserStorage key={s.Id} userdetails={this.props.userdetails} storage={s} requestQuota={this.props.requestQuota} />) })
                }
                </Card.Body>
              </Card>
            </Row>
            <Row>
              <Card className="px-0">
                <Card.Header>Public HTML</Card.Header>
                <Card.Body>
                <Row className="mt-2"><Col>{this.props.userdetails.publichtml ? (<span>Your public HTML pages are viewable here - <a href={this.publichtmlurl}>{this.publichtmlurl}</a>. You can edit your public HTML files here <code>{this.publichtmlfolder}</code></span>) : "You have not turned on the public html space"}</Col>
                <Col md={3}>
                  {
                    this.props.userdetails.publichtml ? (<span></span>) : (<Button className="my-2" disabled={true} variant="secondary" onClick={this.showPublicHTML}>Request</Button>)
                  }
                </Col>
                </Row>
                </Card.Body>
              </Card>
              </Row>
              <Row>
                <Card className="px-0">
                  <Card.Header>Audit Trail</Card.Header>
                  <Card.Body>Click <NavLink to={"/myaudittrail"}>here</NavLink> to see a history of changes to this user account.
                  </Card.Body>
                </Card>
              </Row>
          </Col>
        </Row>
        <Row>
          <Col className="mx-2">
              <Row>
                <Card className="px-0">
                  <Card.Header>SSH Public Keys</Card.Header>
                  <Card.Body>
                    <SSHKeysComponent username={this.props.userdetails.username}></SSHKeysComponent>
                  </Card.Body>
                </Card>
              </Row>
          </Col>
        </Row>
      </Container>
      </>
    );
  }
}


export default function MyProfile() {
  const { loading, error, data } = useQuery(HOMEDETAILS, { errorPolicy: 'all'} );
  const [ chgShellfn ] = useMutation(CHANGE_USER_SHELL_MUTATION);
  const [ updtEppnfn ] = useMutation(USER_UPDATE_EPPN_MUTATION);
  const [ updtUserfn ] = useMutation(USER_UPDATE_USER);
  const [ quotafn ] = useMutation(QUOTA_REQUEST);
  const [ chgPublicHtml ] = useMutation(CHANGE_PUBLIC_HTML_MUTATION);

  const [chgShellShow, setChgShellShow] = useState(false);
  const [updtEppnShow, setUpdtEppnShow] = useState(false);
  const [updtPrefEmail, setUpdtPrefEmail] = useState(false);
  const [enblPublicHtml, setEnblPublicHtml] = useState(false);

  console.log("Using the SSH MFA key service at " + SSHKeysService);

  const userChangeShell = (newshell) => {
    console.log("Requesting a change to user shell to " + newshell);
    chgShellfn({ variables: { request: { reqtype: "UserChangeShell", shell: newshell } }, refetchQueries: [ HOMEDETAILS, 'whoami' ]});
    setChgShellShow(false);
  };

  const userChangePublicHtml = (enable, callWhenDone, onError) => {
    console.log("Requesting a change to  " + (enable ? "enable" : "disable")  + " public html");
    chgPublicHtml({ variables: { request: { reqtype: "UserPublicHtml", publichtml: enable } }, 
      onCompleted: (data) => { console.log(data); callWhenDone(data)},
      onError: (error) => { console.log(error); onError(error.message)}, 
      refetchQueries: [ HOMEDETAILS, 'whoami' ]});
  };

  const updateEppns = (neweppns, onerrorfunction) => {
    console.log("Changing EPPNs to " + _.join(neweppns, ","));
    updtEppnfn({ variables: { eppns: neweppns }, refetchQueries: [ HOMEDETAILS, 'whoami' ], onError: (error) => { onerrorfunction(error); }});
  };

  const changePreferredEmail = (newpreferredemail) => {
    console.log("Changing preferred email to " + newpreferredemail);
    updtUserfn({ variables: { user: { Id: data["whoami"]["Id"], username: data["whoami"]["username"], preferredemail: newpreferredemail } }, refetchQueries: [ HOMEDETAILS, 'whoami' ]});
    setUpdtPrefEmail(false);
  };

  const requestQuota = (storagename, gigabytes, purpose, notes) => {
    console.log("Putting in a request for changing the quota");
    quotafn({ variables: { request: { reqtype: "UserStorageAllocation", storagename: storagename, gigabytes: gigabytes, purpose: purpose, notes: notes }}});
  };

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  console.log(data);

  return (
    <>
      <ChangeUserShell show={chgShellShow} setShow={setChgShellShow} userdetails={data["whoami"]} userChangeShell={userChangeShell} />
      <AddRemoveEPPNs show={updtEppnShow} setShow={setUpdtEppnShow} userdetails={data["whoami"]} updateEppns={updateEppns} />
      <ChangePreferredEmail show={updtPrefEmail} setShow={setUpdtPrefEmail} userdetails={data["whoami"]} changePreferredEmail={changePreferredEmail} />
      <RequestPublicHTML show={enblPublicHtml} setShow={setEnblPublicHtml} userdetails={data["whoami"]} userChangePublicHtml={userChangePublicHtml} />
      <UserDetails userdetails={data["whoami"]} setChgShellShow={setChgShellShow} setUpdtEppnShow={setUpdtEppnShow} setUpdtPrefEmail={setUpdtPrefEmail} setEnblPublicHtml={setEnblPublicHtml} requestQuota={requestQuota}/>
    </>
  );
}
