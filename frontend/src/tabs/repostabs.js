import _ from "lodash";
import React, { Component, useState } from 'react';
import { Link, Outlet } from "react-router-dom";
import { useQuery, useMutation, gql, useLazyQuery } from "@apollo/client";
import Tab from 'react-bootstrap/Tab';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';
import Modal from 'react-bootstrap/Modal';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import { ToolbarButton } from './widgets'

import ReposComputeListView from "./reposcompute";
import ReposStorageListView from "./reposstorage";

const WHOAMI = gql`
query{
  whoami {
    username
    eppns
    isAdmin
    facilities
  }
  facilities {
    name
  }
}`;

const ALL_REPOS = gql`
query {
  allreposandfacility {
    facility
    name
  }
}`;


const REQUEST_REPOMEMBERSHIP_MUTATION = gql`
mutation requestRepoMembership($request: CoactRequestInput!){
  requestRepoMembership(request: $request){
    Id
  }
}
`;
const REQUEST_NEWREPO_MUTATION = gql`
mutation requestNewRepo($request: CoactRequestInput!){
  requestNewRepo(request: $request){
    Id
  }
}
`;

const REQUEST_FACILTY_ACCESS_MUTATION = gql`
mutation requestNewSDFAccount($request: CoactRequestInput!){
  requestNewSDFAccount(request: $request){
    Id
  }
}
`;

class ReqRepMembership extends Component {
  constructor(props) {
    super(props);
    this.state = { reponame: "", reponameInvalid: false, facility: "", facilityInvalid: false }
    this.handleClose = () => { this.props.setShow(false); }
    this.requestRepoMembership = () => {
      console.log(this.state.reponame);
      if(_.isEmpty(this.state.reponame)) {
        this.setState({ reponameInvalid: true });
        return;
      }
      if(_.isEmpty(this.state.facility)) {
        this.setState({ facilityInvalid: true });
        return;
      }
      console.log(props.allreposquery);
      props.allreposquery({
        onCompleted: (data) => {
          if(_.findIndex(data.allreposandfacility, { "facility": this.state.facility, "name": this.state.reponame }) < 0) {
            this.setState({ reponameInvalid: true });
            return;
          }
          this.props.requestRepoMembership(this.state.reponame, this.state.facility);
          this.props.setShow(false);    
        }
      })
    }
    this.setRepoName = (event) => { this.setState({ reponame: event.target.value }) }
    this.setFacility = (event) => { this.setState({ facility: event.target.value }) }

  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Request membership in repo</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row>
            <Col md={2}><Form.Label className="px-2" >Repo:</Form.Label></Col>
            <Col>
              <InputGroup hasValidation>
                <Form.Control type="text" placeholder="Enter name of the repo" onChange={this.setRepoName} isInvalid={this.state.reponameInvalid}/>
                <Form.Control.Feedback type="invalid">Please enter a valid repo name. If you do not know the reponame, please ask your PI for the name.</Form.Control.Feedback>
              </InputGroup>
            </Col>
          </Row>
          <Row>
            <InputGroup hasValidation>
                <Col md={3}><Form.Label className="px-2" >Facility:</Form.Label></Col>
                <Col>
                  <Form.Control required as="select" type="select" onChange={this.setFacility} isInvalid={this.state.facilityInvalid}>
                  <option value="">Please select a facility</option>
                  {
                    _.map(_.sortBy(this.props.facilities), function(x){ return ( <option key={x} value={x}>{x}</option> ) })
                  }
                  </Form.Control>
                  <Form.Control.Feedback type="invalid">Please select a facility</Form.Control.Feedback>
                </Col>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.requestRepoMembership}>
            Request Repo Membership
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class ReqNewRepo extends Component {
  constructor(props) {
    super(props);
    this.state = { reponame: "", reponameInvalid: false, facility: "", facilityInvalid: false, principal: this.props.username, principalInvalid: "" }
    this.handleClose = () => { this.props.setShow(false); }
    this.requestNewRepo = () => {
      console.log(this.state);
      if(_.isEmpty(this.state.reponame)) {
        this.setState({ reponameInvalid: true });
        return;
      }
      if(!/^[\w-_]+$/.test(this.state.reponame)) {
        this.setState({ reponameInvalid: true });
        return;
      }


      this.setState({ reponameInvalid: false });
      if(_.isEmpty(this.state.facility)) {
        this.setState({ facilityInvalid: true });
        return;
      }
      if(_.isEmpty(this.state.principal)) {
        this.setState({ principalInvalid: true });
        return;
      }

      this.props.requestNewRepo({reponame: this.state.reponame, facility: this.state.facility, principal: this.state.principal});
      this.props.setShow(false);
    }
    this.setRepoName = (event) => { this.setState({ reponame: event.target.value }) }
    this.setFacility = (event) => { this.setState({ facility: event.target.value }) }
    this.setPrincipal = (event) => { this.setState({ principal: event.target.value }) }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Request new repo</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row>
            <InputGroup hasValidation>
                <Col md={3}><Form.Label className="px-2" >Repo name:</Form.Label></Col>
                <Col>
                  <Form.Control type="text" placeholder="Enter name of the repo" onChange={this.setRepoName} isInvalid={this.state.reponameInvalid}/>
                  <Form.Control.Feedback type="invalid">Please enter a valid repo name (alphanumeric - and _ ok) </Form.Control.Feedback>
                </Col>
            </InputGroup>
          </Row>
          <Row>
            <InputGroup hasValidation>
                <Col md={3}><Form.Label className="px-2" >Facility:</Form.Label></Col>
                <Col>
                  <Form.Control required as="select" type="select" onChange={this.setFacility} isInvalid={this.state.facilityInvalid}>
                  <option value="">Please select a facility</option>
                  {
                    _.map(this.props.facilities, function(x){ return ( <option key={x} value={x}>{x}</option> ) })
                  }
                  </Form.Control>
                  <Form.Control.Feedback type="invalid">Please select a facility</Form.Control.Feedback>
                </Col>
            </InputGroup>
          </Row>
          <Row>
            <InputGroup hasValidation>
              <Col md={3}><Form.Label className="px-2" >Principal:</Form.Label></Col>
              <Col>
                <Form.Control type="text" placeholder="Enter principal's userid" value={this.state.principal} onChange={this.setPrincipal} isInvalid={this.state.principalInvalid}/>
                <Form.Control.Feedback type="invalid">Please enter a valud userid</Form.Control.Feedback>
                </Col>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.requestNewRepo}>
            Request Repo
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}


class ReqFacilityAccess extends Component {
  constructor(props) {
    super(props);
    this.state = { facility: "", isError: false, errorMsg: "", isDone: false, requestContext: "", contextInvalid: false }
    this.handleClose = () => { this.props.setShow(false); }
    let timer = null;
    this.requestFacilityAccess = () => {
      console.log(this.state.facility);
      if(_.isEmpty(this.state.facility)) {
        this.setState({ isError: true, errorMsg: "Please choose a valid facility" });
        return;
      }
      if(_.isEmpty(this.state.requestContext)) {
        this.setState({contextInvalid: true});
        return;
      }
      this.props.requestFacilityAccess(this.state.facility, this.state.requestContext,
        () => { 
          this.setState({isDone: true}); 
          timer = setTimeout(() => this.props.setShow(false), 3000)
        },
        (error) => { 
          this.setState({isError: true, errorMsg: error.message});
        }
      );
    }
    this.setFacility = (event) => { this.setState({ facility: event.target.value, isError: false, errorMsg: "" }) }
    this.setRequestContext = (event) => { this.setState({ requestContext: event.target.value }) }

  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Request access to facility</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {this.state.isDone ? <Alert key={"success"} variant={"success"}><p>A request for access to the facility <b>{this.state.facility}</b> has been made.</p><p>You should be able to access the resources in the facility once this has been approved.</p></Alert> : ""}
          <Row>
            <Form.Text className="py-2">Please choose a facility</Form.Text>
            <InputGroup hasValidation>
              <Form.Control required as="select" type="select" onChange={this.setFacility} isInvalid={this.state.isError}>
                <option value="">Please select a facility</option>
                {
                  _.map(_.sortBy(this.props.facilities), function(x){ return ( <option key={x} value={x}>{x}</option> ) })
                }
              </Form.Control>
              <Form.Control.Feedback type="invalid">{this.state.errorMsg}</Form.Control.Feedback>
              </InputGroup>
              </Row>
              <Row>
              <InputGroup hasValidation>
              <Form.Text className="py-2">{this.state.facilityDescription}</Form.Text>
                  <Form.Text className="py-2">Please provide some context for your S3DF account request</Form.Text>
                  <InputGroup>
                    <Form.Control as="textarea" rows={3}  
                      onChange={this.setRequestContext}
                      isInvalid={this.state.contextInvalid}
                      placeholder="I am a PhD student in Dr. A's lab working on project Z and need compute resources to run simulations"/>
                      <Form.Control.Feedback type="invalid">Please provide some context.</Form.Control.Feedback>
                  </InputGroup>
            </InputGroup>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.requestFacilityAccess}>
            Request Facility Access
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

export default function RepoTabs(props) {
  const { loading, error, data } = useQuery(WHOAMI);
  const [ allreposquery ] = useLazyQuery(ALL_REPOS);
  const [repMemShow, setRepMemShow] = useState(false);
  const [newRepShow, setNewRepShow] = useState(false);
  const [facAccShow, setFacAccShow] = useState(false);
  const [toolbaritems, setToolbaritems] = useState([
    ["Request Access to Facility", setFacAccShow ],
    ["Request Repo Membership", setRepMemShow ],
    ["Request New Repo", setNewRepShow ]
  ]);
  const [statusbaritems, setStatusbaritems] = useState([]);
  const [ repomemnrshipfn ] = useMutation(REQUEST_REPOMEMBERSHIP_MUTATION);
  const [ newrepofn ] = useMutation(REQUEST_NEWREPO_MUTATION);
  const [ facaccessfn ] = useMutation(REQUEST_FACILTY_ACCESS_MUTATION);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  console.log(data);

  let username = _.get(data, "whoami.username");
  let isadmin = _.get(data, "whoami.isAdmin", false);
  let facilities = _.map(_.get(data, "facilities"), "name");
  let myfacilities = isadmin ? facilities : _.get(data, "whoami.facilities");
  let mymissingfacilties = _.difference(facilities, _.get(data, "whoami.facilities"));

  const requestRepoMembership = (reponame, facilityname) => {
    console.log("Repo membership requested for repo " + reponame + " in facility" + facilityname);
    repomemnrshipfn({ variables: { request: { reqtype: "RepoMembership", reponame: reponame, facilityname: facilityname }}});
    setRepMemShow(false);
  };

  const requestNewRepo = (repodetails) => {
    console.log("New repo requested Name: " + repodetails["reponame"] + " Facility: " + repodetails["facility"] + " Principal: " + repodetails["principal"]);
    newrepofn({ variables: { request: { reqtype: "NewRepo", reponame: repodetails.reponame, facilityname: repodetails.facility, principal: repodetails.principal }}});
    setNewRepShow(false);
  };

  const requestFacilityAccess = (facility, requestContext, onSuccess, onError) => {
    console.log("Access requsted to facility " + facility);
    facaccessfn({ variables: { request: { reqtype: "UserAccount", eppn: _.get(data, "whoami.eppns[0]", username + "@slac.stanford.edu"), preferredUserName: username, "facilityname": facility, notes: requestContext }}, 
      onCompleted: onSuccess, onError: (error) => { onError(error)}});
    setNewRepShow(false);
  };

  return (<Tab.Container activeKey={props.reposActiveTab}>
        <Row id="repotabs">
          <Col md={2}>
            <Nav variant="tabs" onSelect={(selKey) => { props.setReposActiveTab(selKey); }}>
            <Nav.Item>
                <Nav.Link eventKey="info" as={Link} to={`info`}>Info</Nav.Link>
              </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="compute" as={Link} to={`compute`}>Compute</Nav.Link>
                </Nav.Item>
              </Nav>
            </Col>
            <Col>
              <span className="statusbar me-1 align-bottom">
              </span>
              <span className="float-end me-1">
              { _.map(statusbaritems, (x, i) => { return <span key={`statusbar_${i}`} className="item px-1">{x}</span> }) }
              {
                _.map(toolbaritems, (x) => { return <ToolbarButton key={x[0]} label={x[0]} setShow={x[1]} /> })
              }
              </span>
            </Col>
        </Row>
        <Tab.Content>
          <Outlet context={[toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems]}/>
        </Tab.Content>
        <ReqRepMembership show={repMemShow} setShow={setRepMemShow} username={username} requestRepoMembership={requestRepoMembership} facilities={myfacilities} allreposquery={allreposquery} />
        <ReqNewRepo show={newRepShow} setShow={setNewRepShow} username={username} requestNewRepo={requestNewRepo}  facilities={myfacilities}/>
        <ReqFacilityAccess show={facAccShow} setShow={setFacAccShow} username={username} requestFacilityAccess={requestFacilityAccess}  facilities={mymissingfacilties}/>
    </Tab.Container>);
}
