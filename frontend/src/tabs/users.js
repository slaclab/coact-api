import React, { useState } from "react";
import { useQuery, useMutation, useLazyQuery, gql } from "@apollo/client";
import { Link, useParams, useOutletContext } from "react-router-dom";
import { BulkSearchAndAdd } from "./widgets";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import ModalHeader from 'react-bootstrap/ModalHeader';
import ModalBody from 'react-bootstrap/ModalBody';
import ModalFooter from 'react-bootstrap/ModalFooter';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import { faPersonArrowUpFromLine, faPersonArrowDownToLine, faClipboard, faTrash } from '@fortawesome/free-solid-svg-icons'
import _ from "lodash";

const REPODETAILS = gql`
query Repos($reposinput: RepoInput){
  repos(filter:$reposinput) {
    name
    facility
    facilityObj {
      czars
    }    
    principal
    leaders
    users
    allUsers {
      Id
      username
      uidnumber
      preferredemail
      fullname
      eppnObjs {
        eppn
        fullname
        organization
      }
    }
  }
  whoami {
    username
  }
}
`;

const USERMATCHINGUSERNAMES = gql`
query usersMatchingUserNames($regexes: [String!]!) {
  usersMatchingUserNames(regexes: $regexes) {
    username
  }
}`;

const TOGGLE_ROLE_MUTATION = gql`
mutation ToggleUserRole($reposinput: RepoInput!, $user: UserInput!){
  repoToggleUserRole(repo: $reposinput, user: $user){
    name
    leaders
  }
}
`;

const ADD_USER_MUTATION = gql`
mutation AddUserToRepo($reposinput: RepoInput!, $user: UserInput!) {
  repoAddUser(repo: $reposinput, user: $user) {
    name
  }
}
`;

const REMOVE_USER_MUTATION = gql`
mutation AddUserToRepo($reposinput: RepoInput!, $user: UserInput!) {
  repoRemoveUser(repo: $reposinput, user: $user) {
    name
  }
}
`;


class Eppn extends React.Component {
  render() {
    return _.map(_.get(this.props.user, "eppnObjs", []), (e, i) => {
      return(
        <div key={e.fullname} className="row">
          <span className="col-4">{(i == 0) ? this.props.user.fullname : ""}</span>
          <span className="col-4">{(i == 0) ? this.props.user.preferredemail : ""}</span>
          <span className="col-4">{e.eppn}</span>
        </div>
      )
    })
  }
}

class ManageRoleAction extends React.Component {
  constructor(props) {
    super(props);
    let user = this.props.user;
    this.state = { is_leader: user.is_leader, maximal_role: user.maximal_role }

    this.handleRoleChange = (event) => {
      let donefn = (data) => {
        console.log("Done function...");
        let leaders = _.get(data, "repoToggleUserRole.leaders", []);
        let is_leader = _.includes(leaders, user.username);
        let maximal_role = is_leader ? "Leader" : "User";
        this.setState({ is_leader: is_leader, maximal_role: maximal_role })
      }
      this.props.onToggleRole(user.username, donefn);
    }
  }

  render() {
    let user = this.props.user;
    var act = (<span/>);
    if(user.has_manage_roles) {
      if(this.state.is_leader) {
        act = (<span className="inlntlbr select_role px-2 text-warning" title="Remove the leader role for this user" onClick={this.handleRoleChange}><FontAwesomeIcon icon={faPersonArrowDownToLine}/></span>)
      } else {
        act = (<span className="inlntlbr select_role px-2 text-warning" title="Add the leader role to this user" onClick={this.handleRoleChange}><FontAwesomeIcon icon={faPersonArrowUpFromLine}/></span>)
      }
    }
    return (
      <span>{user.is_pi ? "PI" : this.state.maximal_role}
        <span>{user.is_pi ? "" : act}</span>
      </span>
    )
  }
}

class DeleteUserAction extends React.Component {
  constructor(props) {
    super(props);
    let user = this.props.user;
    this.state = { is_leader: user.is_leader, maximal_role: user.maximal_role }

    this.deleteUser = (event) => {
      if(user.is_pi) {
        alert("NoNo");
        return;
      }
      let donefn = (data) => {
        console.log("Done function...");
        let leaders = _.get(data, "repoToggleUserRole.leaders", []);
        let is_leader = _.includes(leaders, user.username);
        let maximal_role = is_leader ? "Leader" : "User";
        this.setState({ is_leader: is_leader, maximal_role: maximal_role })
      }
      this.props.removeUserFromRepo(user.username, donefn);
    }
  }

  render() {
    let user = this.props.user;
    if(this.props.user.is_pi) {
      return (<span/>);
    }
    return (<span className="inlntlbr select_role px-2 text-warning float-end" title="Remove this user from the repo" onClick={this.deleteUser}><FontAwesomeIcon icon={faTrash}/></span>);
  }
}

class UsersTab extends React.Component {
  constructor(props) {
    super(props);
    this.state = { showToast: false, toastMsg: "" }
    this.hideModal = () => {
      this.props.setShowModal(false);
    }

    this.getusernamematches = (srchtxts, onCompleted) => {
      this.props.getUsersMatchingUserNames({
        variables: { regexes: srchtxts},
        onCompleted: (data) => {
          let matches = _.map(_.get(data, "usersMatchingUserNames", []), "username");
          onCompleted(matches);
        }
      })
    }

    this.copyJustTheUserNamesToTheClipboard = () => {
      let usernames = _.join(_.sortBy(_.map(this.props.users, "username")), "\n");
      navigator.clipboard.writeText(usernames);
      this.setState({showToast: true, toastMsg: "Copied"})
    }
  }

  componentDidMount() {
    if(this.props.amILeader || this.props.amICzar) {
      this.props.setToolbaritems(oldItems => [...oldItems, ["Manage Users", this.props.setShowModal]]);
    }
  }

  componentWillUnmount() {
    this.props.setToolbaritems(oldItems => _.filter(oldItems, (x) => { return x[0] != "Manage Users" }));
  }

  render() {
    return (
      <div className="container-fluid tabcontainer">
        <Modal backdrop="static" show={this.props.showModal} onHide={this.hideModal} size="lg">
            <ModalHeader closeButton={true}>
              <Modal.Title>Search for users and add/remove them to/from this repo.</Modal.Title>
            </ModalHeader>
            <ModalBody>
              <div className="mb-2">Add/remove one or more users to the repo. We use regex matches; so patterns like <code>mar.*</code> can be used. 
              Type in or paste a paste a list of users into the textbox hit <b>Lookup</b> to look up their user accounts. Then select/unselect and hit <b>Apply</b> to actually make the change to the repo.</div>
              <BulkSearchAndAdd label="Username" getmatches={this.getusernamematches}  selected={_.map(this.props.users, "username")} onSelDesel={this.props.onSelDesel} hideModal={this.hideModal}/>
            </ModalBody>
            <ModalFooter>
            </ModalFooter>
        </Modal>
        <div className="container-fluid" id="users_content">
          <Row>
            <Col><div className="brdcrmb"><Link to={"../info"}>Users</Link> / {this.props.repodata.name}</div></Col>
            <Col><div className="sectiontitle">Users for repo <span className="ref">{this.props.repodata.name}</span></div></Col>
            <Col className="mb-2">
            </Col>
          </Row>
          <div className="table-responsive">
            <table className="table table-condensed table-striped table-bordered collabtbl">
              <thead>
                <tr>
                  <th>Userid<span className="float-end bg-warning" title="Copy the list of users to the clipboard" onClick={this.copyJustTheUserNamesToTheClipboard}><FontAwesomeIcon className="mx-2 my-1 navtxt" icon={faClipboard}/></span></th>
                  <th>Role</th>
                  <th colSpan="3">
                    <div className="row">
                      <span className="col-4">Full name</span>
                      <span className="col-4">User preferred email</span>
                      <span className="col-4">EPPN</span>
                    </div>
                  </th>
                  <th>Account state</th>
                  <th>Created</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
              {_.map(this.props.users, (user) => {
                return (<tr key={user.username}>
                  <td>{user.username}<DeleteUserAction user={user} removeUserFromRepo={this.props.removeUserFromRepo}/></td>
                  <td><ManageRoleAction user={user} onToggleRole={this.props.onToggleRole}/></td>
                  <td colSpan="3"><Eppn user={user}/></td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>)})}
              </tbody>
            </table>
          </div>
        </div>
        <ToastContainer className="p-3" position={"top-end"} style={{ zIndex: 1 }}>
          <Toast show={this.state.showToast} onClose={() => { this.setState({showToast: false, toastMsg: ""})}} delay={3000} autohide><Toast.Header>Info</Toast.Header><Toast.Body>{this.state.toastMsg}</Toast.Body></Toast>
        </ToastContainer>
      </div>
    );
  }
}


export default function Users(props) {
  let params = useParams(), reponame = params.name, facilityname = params.facility;
  const { loading, error, data } = useQuery(REPODETAILS, { variables: { reposinput: { name: reponame, facility: facilityname } } });
  const [ getUsersMatchingUserNames ] = useLazyQuery(USERMATCHINGUSERNAMES, { fetchPolicy: "no-cache" });

  const [ toggleRoleMutation ] = useMutation(TOGGLE_ROLE_MUTATION);
  const [ addUserMutation ] = useMutation(ADD_USER_MUTATION);
  const [ removeUserMutation ] = useMutation(REMOVE_USER_MUTATION);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [ toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems ] = useOutletContext();

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;
  let repodata = data.repos[0], logged_in_user=data.whoami["username"];
  console.log(repodata);

  let leaders = _.get(repodata, "leaders", []), allusers = _.cloneDeep(_.get(repodata, "allUsers", [])), principal = _.get(repodata, "principal");
  let has_manage_roles_privilege = _.includes(_.concat(leaders, [principal]), logged_in_user);
  _.each(allusers, x => {
    x["is_pi"] = x["username"] === principal;
    x["is_leader"] = _.includes(leaders, x["username"]);
    x["maximal_role"] = x["is_leader"] ? "Leader" : "User";
    x["has_manage_roles"] = has_manage_roles_privilege;
  });
  console.log(allusers);
  let amILeader = _.includes(leaders, logged_in_user) || principal==logged_in_user;
  let amICzar = _.includes(_.get(repodata, "facilityObj.czars", []), logged_in_user);

  let toggleRole = function(username, callWhenDone) {
    console.log("Toggling role for user " + username);
    toggleRoleMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: username } }, onCompleted: callWhenDone, onError: (error) => { console.log("Error when toggling role " + error); } });
  }

  let addRemoveUser = function(username, selected) {
    if(selected) {
      console.log("Adding user " + username + " to the repo " + reponame);
      addUserMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: username } }, refetchQueries: [ REPODETAILS, 'Repos' ], onError: (error) => { console.log("Error when toggling role " + error); } });
    } else {
      console.log("Removing user " + username + " from the repo " + reponame);
      removeUserMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: username } }, refetchQueries: [ REPODETAILS, 'Repos' ], onError: (error) => { console.log("Error when toggling role " + error); } });
    }
  }

  let removeUserFromRepo = function(username) { 
    console.log("Removing user " + username + " from the repo " + reponame);
    removeUserMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: username } }, refetchQueries: [ REPODETAILS, 'Repos' ], onError: (error) => { console.log("Error when toggling role " + error); } });
  }

  return (<UsersTab repodata={repodata} users={allusers} getUsersMatchingUserNames={getUsersMatchingUserNames}
    onToggleRole={toggleRole} onSelDesel={addRemoveUser} amILeader={amILeader} amICzar={amICzar}
    showModal={showAddUserModal} setShowModal={setShowAddUserModal}
    toolbaritems={toolbaritems} setToolbaritems={setToolbaritems} removeUserFromRepo={removeUserFromRepo}
    />);
}
