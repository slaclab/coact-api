import React, { Component, useState } from 'react';
import _ from "lodash";
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Modal from 'react-bootstrap/Modal';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import { Navigate } from "react-router-dom";
import Alert from 'react-bootstrap/Alert';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faRocket, faPerson, faPersonCircleQuestion } from '@fortawesome/free-solid-svg-icons'
import { NoNavHeader, Footer } from "./tabs/widgets";
import { useQuery, useMutation, gql } from "@apollo/client";

const FACNAMES = gql`
query facilityNames {
  facilityNameDescs {
    name
    description
  }
  amIRegistered {
    isRegistered
    isRegistrationPending
    eppn
    username
    fullname
    requestObj {
      Id
      approvalstatus
      preferredUserName
      eppn
      facilityname
      notes
      audit {
        notes
      }
    }
  }
}
`;


const REQUEST_USERACCOUNT_MUTATION = gql`
mutation requestNewSDFAccount($request: CoactRequestInput!){
  requestNewSDFAccount(request: $request){
    Id
  }
}
`;

const APPROVE_REQUEST_MUTATION = gql`
mutation ApproveRequest($Id: String!){
  requestApprovePreApproved(id: $Id)
}
`;


class ReqUserAccount extends Component {
  constructor(props) {
    super(props);
    this.handleClose = () => { this.props.setShow(false); }
    this.requestAccount = () => {
      const selFac = this.state.facility, requestContext = this.state.requestContext;
      if(_.isEmpty(selFac) || !_.includes(_.map(this.props.facilityNameDescs, "name"), selFac)) {
        this.setState({facilityInvalid: true});
        return;
      }

      if(_.isEmpty(requestContext)) {
        this.setState({contextInvalid: true});
        return;
      }

      this.props.requestUserAccount(selFac, requestContext,
        () => { this.props.setShow(false); }, 
        (errormsg) => { if(errormsg.message.includes('requests already exists')) { this.setState({showError: true, errorMessage: "A request already exists and is pending for this facility"}) } else { this.setState({showError: true, errorMessage: errormsg.message})}});
    }
    this.state = { facility: "", facilityInvalid: false, facilityDescription: "", showError: false, errorMessage: "", requestContext: "", contextInvalid: false }
    this.setFacility = (event) => { this.setState({ facility: event.target.value, facilityDescription: _.get(_.find(props.facilityNameDescs, ["name", event.target.value]), "description") }); }
    this.setRequestContext = (event) => { this.setState({ requestContext: event.target.value }) }
  }

  render() {
    return (
      <Modal backdrop="static" className="registerMdl" show={this.props.show} onHide={this.handleClose} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Request a S3DF account</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="mb-3">
            <Form.Text>Enable your EPPN <span className="text-primary"><b>{this.props.eppn}</b></span> for the S3DF</Form.Text>
            <Alert className={this.state.showError ? "" : "d-none"} variant={'warning'}>{this.state.errorMessage}</Alert>
            <InputGroup hasValidation>
              <Form.Select name="facility" onChange={this.setFacility} isInvalid={this.state.facilityInvalid}>
                <option value="">Please choose a facility</option>
                { _.map(_.sortBy(this.props.facilityNameDescs, "name"), (f) => { return (<option key={f.name} value={f.name}>{f.name}</option>)}) }
              </Form.Select>
              <Form.Control.Feedback type="invalid">Please choose a valid facility.</Form.Control.Feedback>
            </InputGroup>
            <Form.Text className="py-2 facdesc">{this.state.facilityDescription}</Form.Text>
            <Form.Text className="py-2">Please provide some context for your S3DF account request</Form.Text>
            <InputGroup>
              <Form.Control as="textarea" rows={3}  
                onChange={this.setRequestContext}
                isInvalid={this.state.contextInvalid}
                placeholder="I am a PhD student in Dr. A's lab working on project Z and need compute resources to run simulations"/>
                <Form.Control.Feedback type="invalid">Please provide some context.</Form.Control.Feedback>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>Close</Button>
          <Button type="submit" onClick={this.requestAccount} >Request Account</Button>
        </Modal.Footer>
      </Modal>
      )
  }
}

export default function RegisterUser(props) {
  const { loading, error, data } = useQuery(FACNAMES);
  const [ requestUserAccount, { uudata, uuloading, uuerror }] = useMutation(REQUEST_USERACCOUNT_MUTATION);
  const [ requestApproveMutation ] = useMutation(APPROVE_REQUEST_MUTATION);
  const [show, setShow] = useState(false);
  const handleClose = () => setShow(false);
  const handleShow = () => setShow(true);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;
  console.log(data)

  let hasUserAcc = _.get(data, "amIRegistered.isRegistered", false);
  let eppn = _.get(data, "amIRegistered.eppn", null);
  let username = _.get(data, "amIRegistered.username", null);
  let registrationPending = _.get(data, "amIRegistered.isRegistrationPending", false);
  let isRegistered = _.get(data, "amIRegistered.isRegistered", false);
  let fullname = _.get(data, "amIRegistered.fullname", "");
  let isRegistrationApproved = _.get(data, "amIRegistered.requestObj.approvalstatus", "") == "Approved";
  let isRegistrationPreapproved = _.get(data, "amIRegistered.requestObj.approvalstatus", "") == "PreApproved";
  let isRegistrationRejected = _.get(data, "amIRegistered.requestObj.approvalstatus", "") == "Rejected";
  let notes = _.get(data, "amIRegistered.requestObj.audit[0].notes", "");
  

  const requestAccount = (selectedFacility, requestContext, onSuccess, onError) => {
    const preferredUserName = username;
    console.log("Account requested for eppn " + eppn + " in facility "  + selectedFacility + " with preferred username " + preferredUserName);
    requestUserAccount({ variables: { request: { reqtype: "UserAccount", eppn: eppn, preferredUserName: preferredUserName, "facilityname": selectedFacility, notes: requestContext }}, 
      onCompleted: () => { onSuccess() },
      onError: (error) => { onError(error)},
      refetchQueries: [ FACNAMES, 'amIRegistered' ]});
  };

  if(isRegistered) {
    return (
      <Navigate to="../myprofile" replace />
    );
  }

  if (registrationPending) {
    let preferredUserName = _.get(data, "amIRegistered.requestObj.preferredUserName", "")
    if(isRegistrationPreapproved) {    
      let reqid = _.get(data, "amIRegistered.requestObj.Id", "");
      if (!_.isEmpty(preferredUserName) && eppn==_.get(data, "amIRegistered.requestObj.eppn", "") && !_.isEmpty(reqid)) {
        let approve = function() {
          requestApproveMutation({ 
            variables: { Id: reqid }, 
            onCompleted: () => { setTimeout(() => { window.location.reload() }, 5000)}, 
            onError: (error) => { console.log("Error when approving request " + error); }, 
            refetchQueries: [ FACNAMES, 'amIRegistered' ] });
        }
  
        return (
          <>
          <div className="registeruser d-flex flex-column">
             <NoNavHeader/>
             <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
             <div className="p-2 flex-grow-1">
              Your request to enable the EPPN <span className="text-primary"><b>{eppn}</b></span> using the username <b>{preferredUserName}</b> for the S3DF is pre-approved. 
              To complete the request, please click here <Button variant="secondary" onClick={approve}>Complete Registration</Button>
             </div>
             <Footer/>
          </div>
          </>
        );
      }
    }

    if(isRegistrationRejected) {
      return (
        <>
        <div className="registeruser d-flex flex-column">
          <NoNavHeader/>
          <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
          <div className="p-2 flex-grow-1">
            Your previous request for a user account for <span className="text-primary"><b>{eppn}</b></span> has not been approved.
            If you would like to try again, please click here -
            <button type="button" className="btn btn-primary" onClick={handleShow}>Enable my S3DF account</button>
            <div><i>{notes}</i></div>
          </div>
          <ReqUserAccount show={show} setShow={setShow} eppn={eppn} requestUserAccount={requestAccount} facilityNameDescs={data.facilityNameDescs} />
          <Footer/>
        </div>
        </>
      )    
    }

    if(isRegistrationApproved) {
      setTimeout(() => { window.location.reload() }, 30000);
      return (
      <>
      <div className="registeruser d-flex flex-column">
         <NoNavHeader/>
         <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
         <div className="p-2 flex-grow-1">
          Your request to enable the EPPN <span className="text-primary"><b>{eppn}</b></span> and userid <span className="text-primary"><b>{preferredUserName}</b></span> for S3DF has been approved.
          Your account is still in the process of being created; please check back again in a little while.
         </div>
         <Footer/>
      </div>
      </>)
    }

    return (
      <>
      <div className="registeruser d-flex flex-column">
         <NoNavHeader/>
         <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
         <div className="p-2 flex-grow-1">
          Your request to enable the EPPN <span className="text-primary"><b>{eppn}</b></span> and userid <span className="text-primary"><b>{preferredUserName}</b></span> for S3DF is still pending and will be acted upon soon.
         </div>
         <Footer/>
      </div>
      </>
    );
  }

  if(_.isNil(username)) {
    return (
      <>
      <div className="registeruser d-flex flex-column">
         <NoNavHeader/>
         <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
         <div className="p-2 flex-grow-1">
          We are not able to determine your user id with certainty.
          It's likely that your user account setup has not completed yet or we may be having an outage upstream.
          Could you please try again later?
          If you continue to experience this error, please contact <b>s3df-help@slac.stanford.edu</b>
         </div>
         <Footer/>
      </div>
      </>
    );
  }

  return (
    <>
    <div className="registeruser d-flex flex-column">
      <NoNavHeader/>
      <h6 className="p-2">Hi <span className="text-primary">{fullname}</span>, welcome to Coact; the portal for using the S3DF.</h6>
      <div className="p-2 flex-grow-1">
        You don't seem to have an S3DF account associated with your EPPN <span className="text-primary"><b>{eppn}</b></span> and userid <span className="text-primary"><b>{username}</b></span>.
        If you would like to request your account be enabled for S3DF, please click here -
        <button type="button" className="btn btn-primary" onClick={handleShow}>Enable my S3DF account</button>
      </div>
      <ReqUserAccount show={show} setShow={setShow} eppn={eppn} requestUserAccount={requestAccount} facilityNameDescs={data.facilityNameDescs} />
      <Footer/>
    </div>
    </>
  );
}
