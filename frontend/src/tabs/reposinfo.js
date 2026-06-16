import _ from "lodash";
import { NavLink } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faEdit, faUser, faHistory, faIdBadge, faSliders } from '@fortawesome/free-solid-svg-icons'
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import ModalHeader from 'react-bootstrap/ModalHeader';
import ModalTitle from 'react-bootstrap/ModalTitle';
import ModalBody from 'react-bootstrap/ModalBody';
import ModalFooter from 'react-bootstrap/ModalFooter';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';

const REPOS = gql`
query{
  myRepos {
    name
    facility
    principal
    leaders
    users
    group
    description
  }
  whoami {
    username
    isAdmin
    subjectFacilities
  }
}`;

const UPDATE_REPO_MUTATION = gql`
mutation repoUpdate($reposinput: RepoInput!){
  repoUpdate(repo: $reposinput){
    name
  }
}
`;

const UPDATE_REPO_PI_MUTATION = gql`
mutation repoChangePrincipal($reposinput: RepoInput!, $user: UserInput!){
  repoChangePrincipal(repo: $reposinput, user: $user){
    name
  }
}
`;

const RENAME_REPO_MUTATION = gql`
mutation repoRenameRepo($reposinput: RepoInput!, $newname: String!){
  repoRenameRepo(repo: $reposinput, newname: $newname){
    name
  }
}
`;

const APPROVE_REQUEST_MUTATION = gql`
mutation ApproveRequest($Id: String!){
  requestApprove(id: $Id)
}
`;


class ChangePI extends Component {
  constructor(props) {
    super(props);
    this.state = { newPI: props.repo.princpial, isError: false, errMsg: "" }
    this.changePI = (event) => { this.setState({newPI: event.target.value, isError: false, errMsg: ""}) }
    this.changePIOnServer = () => {
      if(_.isEmpty(this.state.newPI)) {
        this.setState({isError: true, errMsg: "Please choose a valid PI"});
        return;
      }
      this.props.changePI(this.props.repo.name, this.props.repo.facility, this.state.newPI, () => { this.props.setShowModal(false) }, (error) => { console.log(error); this.setState({ isError: true, errMsg: error.message })  } )
    }
  }

  render() {
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.props.setShowModal(false)}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Change the PI for repo <b className="em">{this.props.repo.name}</b> in facility <b className="em">{this.props.repo.facility}</b> </ModalTitle>
        </ModalHeader>
        <ModalBody>
          <InputGroup hasValidation>
            <Form.Select name="newPI" value={this.state.newPI} onChange={this.changePI}  isInvalid={this.state.isError}>
                <option value="">Please choose a new PI</option>
                { _.map(_.sortBy(this.props.repo.users), (s) => { return (<option key={s} value={s}>{s}</option>)}) }
              </Form.Select>
            <Form.Control.Feedback type="invalid">{this.state.errMsg}</Form.Control.Feedback>
          </InputGroup>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.props.setShowModal(false)}}>
            Close
          </Button>
          <Button onClick={this.changePIOnServer}>
            Done
          </Button>
        </ModalFooter>
    </Modal>
    );
  }
}

class ChangeDescription extends Component {
  constructor(props) {
    super(props);
    this.state = { newdescription: props.repo.description, isError: false, errMsg: "" }
    this.changeDescription = (event) => { this.setState({newdescription: event.target.value, isError: false, errMsg: ""}) }
  }

  render() {
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.props.setShowModal(false)}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Change the description for repo <b className="em">{this.props.repo.name}</b> in facility <b className="em">{this.props.repo.facility}</b> </ModalTitle>
        </ModalHeader>
        <ModalBody>
          <InputGroup hasValidation>
            <Form.Control onBlur={this.changeDescription} isInvalid={this.state.isError} defaultValue={this.state.newdescription}/>
            <Form.Control.Feedback type="invalid">{this.state.errMsg}</Form.Control.Feedback>
          </InputGroup>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.props.setShowModal(false)}}>
            Close
          </Button>
          <Button onClick={() => { this.props.changeRepoDescription(this.props.repo.name, this.props.repo.facility, this.state.newdescription, () => { this.props.setShowModal(false) }, (error) => { console.log(error); this.setState({ isError: true, errMsg: error.message })  } ) }}>
            Done
          </Button>
        </ModalFooter>
    </Modal>
    );
  }
}

class ChangeLDAPGroup extends Component {
  constructor(props) {
    super(props);
    this.state = { newgroup: props.repo.group ? props.repo.group : props.repo.name, isError: false, errMsg: "" }
    this.changeGroup = (event) => { this.setState({newgroup: event.target.value, isError: false, errMsg: ""}) }
  }

  render() {
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.props.setShowModal(false)}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Change the LDAP group for repo <b className="em">{this.props.repo.name}</b> in facility <b className="em">{this.props.repo.facility}</b> </ModalTitle>
        </ModalHeader>
        <ModalBody>
          <InputGroup hasValidation>
            <Form.Control onBlur={this.changeGroup} isInvalid={this.state.isError} defaultValue={this.state.newgroup}/>
            <Form.Control.Feedback type="invalid">{this.state.errMsg}</Form.Control.Feedback>
          </InputGroup>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.props.setShowModal(false)}}>
            Close
          </Button>
          <Button onClick={() => { this.props.changeRepoGroup(this.props.repo.name, this.props.repo.facility, this.state.newgroup, () => { this.props.setShowModal(false) }, (error) => { console.log(error); this.setState({ isError: true, errMsg: error.message })  } ) }}>
            Done
          </Button>
        </ModalFooter>
    </Modal>
    );
  }
}


class RenameRepo extends Component {
  constructor(props) {
    super(props);
    this.state = { newname: props.repo.name, isError: false, errMsg: "" }
    this.changeName = (event) => { this.setState({newname: event.target.value, isError: false, errMsg: ""}) }
  }

  render() {
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.props.setShowModal(false)}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Change the name for repo <b className="em">{this.props.repo.name}</b> in facility <b className="em">{this.props.repo.facility}</b> </ModalTitle>
        </ModalHeader>
        <ModalBody>
          <InputGroup hasValidation>
            <Form.Control onBlur={this.changeName} isInvalid={this.state.isError} defaultValue={this.state.newname}/>
            <Form.Control.Feedback type="invalid">{this.state.errMsg}</Form.Control.Feedback>
          </InputGroup>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.props.setShowModal(false)}}>
            Close
          </Button>
          <Button onClick={() => { this.props.renameRepo(this.props.repo.name, this.props.repo.facility, this.state.newname, () => { this.props.setShowModal(false) }, (error) => { console.log(error); this.setState({ isError: true, errMsg: error.message })  } ) }}>
            Done
          </Button>
        </ModalFooter>
    </Modal>
    );
  }
}


class ReposRows extends Component {
  constructor(props) {
    super(props);
    let isAdminOrCzar = this.props.userinfo.isAdmin || _.includes(this.props.userinfo.subjectFacilities, this.props.repo.facility);
    this.state = { 
      showPI: false, 
      showGrp: false, 
      showDesc: false,
      showRenameRepo: false
    };
    this.changePI = (event) => {  this.setState({showPI: true}) }
    this.changeLDAPGroup = (event) => {  this.setState({showGrp: true}) }
    this.changeDescription = (event) => {  this.setState({showDesc: true}) }
    this.renameModal = (event) => {  this.setState({showRenameRepo: true}) }
  }
  render() {
    let isAdminOrCzar = this.props.userinfo.isAdmin || _.includes(this.props.userinfo.subjectFacilities, this.props.repo.facility);  
      return (
        <tr key={this.props.repo.name} className="text-start">
          <td className="vmid px-2">
            {this.props.repo.name}
            <NavLink to={"/repos/features/"+this.props.repo.facility+"/"+this.props.repo.name} className="float-end px-1">
              <span className="text-warning" title="Enable/disable features for this repo"><FontAwesomeIcon icon={faSliders}/></span>
            </NavLink>
            <NavLink to={"/repos/audit/"+this.props.repo.facility+"/"+this.props.repo.name} className="float-end px-1">
              <span className="text-warning" title="See the history of changes to this repo" onClick={this.changePI}><FontAwesomeIcon icon={faHistory}/></span>
            </NavLink>
            <NavLink to={"/repos/users/"+this.props.repo.facility+"/"+this.props.repo.name} className="float-end px-1">
              <span className="text-warning" title="Add/remove users to/from this repo" onClick={this.changePI}><FontAwesomeIcon icon={faUser}/></span>
            </NavLink>
            <span className="float-end px-1" onClick={this.renameModal}>
              <span className="text-warning" title="Rename this repo"><FontAwesomeIcon icon={faIdBadge}/></span>
            </span>
          </td>
          <td className="vmid px-2">{this.props.repo.facility}</td>
          <td className="vmid px-2">{this.props.repo.principal} { isAdminOrCzar ? <span className="float-end"><span className="inlntlbr select_role px-2 text-warning" title="Change the PI for this repo" onClick={this.changePI}><FontAwesomeIcon icon={faEdit}/></span></span> : ""}</td>
          <td className="vmid px-2">{this.props.repo.group} { isAdminOrCzar ? <span className="float-end"><span className="inlntlbr select_role px-2 text-warning" title="Change the LDAP group associated with this repo" onClick={this.changeLDAPGroup}><FontAwesomeIcon icon={faEdit}/></span></span> : ""}</td>
          <td className="vmid px-2">{this.props.repo.description} { isAdminOrCzar ? <span className="float-end"><span className="inlntlbr select_role px-2 text-warning" title="Edit this repo's description" onClick={this.changeDescription}><FontAwesomeIcon icon={faEdit}/></span></span> : ""}</td>
          <ChangePI showModal={this.state.showPI} setShowModal={() => this.setState({showPI: false})} repo={this.props.repo} changePI={this.props.changePI} />
          <ChangeDescription showModal={this.state.showDesc} setShowModal={() => this.setState({showDesc: false})} repo={this.props.repo} changeRepoDescription={this.props.changeRepoDescription} />
          <ChangeLDAPGroup showModal={this.state.showGrp} setShowModal={() => this.setState({showGrp: false})} repo={this.props.repo} changeRepoGroup={this.props.changeRepoGroup} />
          <RenameRepo showModal={this.state.showRenameRepo} setShowModal={() => this.setState({showRenameRepo: false})} repo={this.props.repo} renameRepo={this.props.renameRepo} />
        </tr>
      );
  }
}


class ReposTable extends Component {
  constructor(props) {
    super(props);
    this.state = { showToast: false, toastMsg: "" }
    this.displayConfirmation = (message) => { 
      this.setState({showToast: true, toastMsg: message})
    }
  }
  render() {
    return (
      <>
      <ToastContainer className="p-3" position={"top-end"} style={{ zIndex: 1 }}>
        <Toast show={this.state.showToast} onClose={() => { this.setState({showToast: false, toastMsg: ""})}} delay={10000} autohide><Toast.Header>Info</Toast.Header><Toast.Body>{this.state.toastMsg}</Toast.Body></Toast>
      </ToastContainer>
      <div className="container-fluid text-center">
        <table className="table table-condensed table-striped table-bordered table-responsive">
          <thead>
            <tr><th>Repo name</th><th>Facility</th><th>PI</th><th>LDAP Group</th><th>Description</th></tr>
          </thead>
          <tbody>
            { _.map(this.props.repos, (r) => { return (<ReposRows key={r.facility+"_"+r.name} repo={r} userinfo={this.props.userinfo}
              displayConfirmation={this.displayConfirmation}
              changeRepoDescription={this.props.changeRepoDescription} changeRepoGroup={this.props.changeRepoGroup} changePI={this.props.changePI} renameRepo={this.props.renameRepo} />) }) 
            }
          </tbody>
        </table>
      </div>
      </>
     )
  }
}

export default function ReposInfoListView() {
  const { loading, error, data, refetch } = useQuery(REPOS);
  const [ updateRepoMutation ] = useMutation(UPDATE_REPO_MUTATION);
  const [ changeRepoPIMutation ] = useMutation(UPDATE_REPO_PI_MUTATION);
  const [ renameRepoMutation ] = useMutation(RENAME_REPO_MUTATION);
  const [ approveRequest ] = useMutation(APPROVE_REQUEST_MUTATION);


  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  const changeRepoDescription = (reponame, facilityname, newdescription, onSuccess, onError) => {
    updateRepoMutation({ variables: { reposinput: { name: reponame, facility: facilityname, description: newdescription }}, refetchQueries: [ REPOS ], onCompleted: onSuccess, onError:  onError});
  }

  const changeRepoGroup = (reponame, facilityname, newgroup, onSuccess, onError) => {
    updateRepoMutation({ variables: { reposinput: { name: reponame, facility: facilityname, group: newgroup }}, refetchQueries: [ REPOS ], onCompleted: onSuccess, onError:  onError});
  }

  const changePI = (reponame, facilityname, newPI, onSuccess, onError) => {
    changeRepoPIMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: newPI }}, refetchQueries: [ REPOS ], onCompleted: onSuccess, onError:  onError});
  }

  const renameRepo = (reponame, facilityname, newname, onSuccess, onError) => {
    renameRepoMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, newname: newname }, refetchQueries: [ REPOS ], onCompleted: onSuccess, onError:  onError});
  }



  let userinfo = _.get(data, "whoami");
  console.log(data);
  return (
    <>
    <ReposTable repos={data.myRepos} userinfo={userinfo} changeRepoDescription={changeRepoDescription} changeRepoGroup={changeRepoGroup} changePI={changePI} renameRepo={renameRepo} />
    </>
  );
}
