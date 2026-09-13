import React, { useState } from "react";
import { useParams, Link, useOutletContext } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import dayjs from "dayjs";
import _ from "lodash";
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import ModalHeader from 'react-bootstrap/ModalHeader';
import ModalTitle from 'react-bootstrap/ModalTitle';
import ModalBody from 'react-bootstrap/ModalBody';
import ModalFooter from 'react-bootstrap/ModalFooter';
import Form from 'react-bootstrap/Form';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import { Formik } from 'formik';
import * as yup from 'yup';


const REPODETAILS = gql`
query Repos($reposinput: RepoInput){
  repos(filter:$reposinput) {
    Id
    name
    facility
    principal
    leaders
    allUsers {
      username
    }
    accessGroupObjs {
      name
      gidnumber
      memberObjs {
        username
      }
    }
  }
  whoami {
    username
  }
}
`;

const TOGGLE_GROUPMEMBERSHIP_MUTATION = gql`
mutation ToggleUserRole($reposinput: RepoInput!, $user: UserInput!, $group: AccessGroupInput!){
  repoToggleGroupMembership(repo: $reposinput, user: $user, group: $group){
    name
  }
}
`;

const NEW_USERGROUP_MUTATION = gql`
mutation accessGroupCreate($reposinput: RepoInput!, $grp: AccessGroupInput!){
  accessGroupCreate(repo: $reposinput, accessgroup: $grp){
    name
    gidnumber
  }
}
`;



class AddGroupModal extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {
    let reponame = this.props.reponame, groupnames = this.props.groupnames;
    let schema = yup.object().shape({
      groupName: yup.string().required().test("Check prefix", "Group names must start with the repo name", function () {
        let gn = this.parent["groupName"];
        return gn && gn.startsWith(reponame) ? true : false;
      }).test("Group already exists", "The group name is already being used", function(){
        let gn = this.parent["groupName"];
        return gn && _.includes(groupnames, gn) ? false : true;
      }),
    });
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={this.props.handleClose}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Create a new access group for this repo. The access group name must have the repo name as a prefix.</ModalTitle>
        </ModalHeader>
        <Formik
          validationSchema={schema}
          onSubmit={values => { this.props.handleSubmit(values.groupName); }}
          initialValues={{
            groupName: this.props.reponame + "-"
          }}
          validateOnChange={true}
          validateOnBlur={true}
        >
          {({
            handleSubmit,
            handleChange,
            handleBlur,
            values,
            touched,
            isValid,
            errors,
          }) => (
            <Form noValidate onSubmit={handleSubmit}>
              <ModalBody>
                <Row className="mb-3">
                  <Form.Group as={Col} md="8" controlId="validationFormik01" className="position-relative">
                    <Form.Label>Name</Form.Label>
                    <Form.Control
                      type="text"
                      name="groupName"
                      value={values.groupName}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      isValid={touched.groupName && !errors.groupName}
                      isInvalid={touched.groupName && errors.groupName}
                    />
                    <Form.Control.Feedback type='invalid' tooltip>{errors.groupName}</Form.Control.Feedback>
                  </Form.Group>
                </Row>
              </ModalBody>
              <ModalFooter>
                <Button variant="light" onClick={this.props.handleClose}>Close</Button>
                <Button type="submit">Create group</Button>
              </ModalFooter>
              </Form>
            )}
            </Formik>
      </Modal>
    );
  }
}

class GroupsTab extends React.Component {
  constructor(props) {
    super(props);
    const groupnames = _.map(this.props.groups, "name");
    this.getUserSels = (grpName) => {
      let grpObj = _.find(this.props.groups, ["name", grpName]);
      let selUserNames = _.map(_.get(grpObj, "memberObjs", []), "username");
      let newusrswithsels = _.map(this.props.allUsers, (u) => {
        return { "name": u["username"], "selected": _.includes(selUserNames, u["username"])  }
      })
      return newusrswithsels;
    }
    this.state = { selectedGroup: "", usrswithsels: []}

    if(!_.isEmpty(groupnames)) {
      let grpName = groupnames[0];
      this.state = { selectedGroup: grpName, usrswithsels: this.getUserSels(grpName)}
    }

    this.selGroup = (event) => {
      let grpName = event.currentTarget.dataset.name;
      this.setState({selectedGroup: grpName, usrswithsels: this.getUserSels(grpName)});
    }

    this.checkUncheck = (event) => {
      let selkey = event.target.dataset.selkey;
      this.props.onSelDesel(selkey, this.state.selectedGroup);
      this.setState((currentState) => {
        return _.find(currentState.usrswithsels, ["name", selkey]).selected = event.target.checked;
      })
    }

    this.hideModal = () => {
      this.props.setShowModal(false);
    }

    this.createGroup = (groupName) => {
      console.log("Need to create " + groupName);
      this.props.createNewUserGroup(groupName)
      this.hideModal();
    }
  }

  componentDidMount() {
    if(this.props.amILeader) {
      this.props.setToolbaritems(oldItems => [...oldItems, ["Create new access group", this.props.setShowModal]]);
    }
  }

  componentWillUnmount() {
    this.props.setToolbaritems(oldItems => _.filter(oldItems, (x) => { return x[0] != "Create new access group" }));
  }

  render() {
    if(_.isEmpty(this.props.groups)) {
      return (<div className="container-fluid text-center tabcontainer">
      <AddGroupModal reponame={this.props.reponame} groupnames={this.groupnames} showModal={this.props.showModal}
        handleClose={this.hideModal} handleSubmit={this.createGroup}/>
        <div className="row">This repo does not have any access groups defined</div></div>)
    }

    return (
      <div className="container-fluid tabcontainer">
        <AddGroupModal reponame={this.props.reponame} groupnames={this.groupnames} showModal={this.props.showModal}
        handleClose={this.hideModal} handleSubmit={this.createGroup}/>
        <div>
          <Row>
            <Col><div className="brdcrmb"><Link to={"../groups"}>Access groups</Link> / {this.props.repodata.name}</div></Col>
            <Col><div className="sectiontitle">Groups for repo <span className="ref">{this.props.repodata.name}</span></div></Col>
            <Col className="mb-2">
            </Col>
          </Row>
          <Row>
            <Col>
              <div className="table-responsive">
                <table className="table table-condensed table-striped table-bordered collabtbl">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>GID</th>
                    </tr>
                  </thead>
                  <tbody>{
                    _.map(this.props.groups, (g) => { return (<tr key={g.name} data-name={g.name} onClick={this.selGroup} className={(g.name === this.state.selectedGroup) ? "bg-secondary": ""}><td>{g.name}</td><td>{g.gidnumber}</td></tr>) })
                  }
                  </tbody>
                </table>
              </div>
            </Col>
            <Col>
              <div className="table-responsive">
                <table className="table table-condensed table-striped table-bordered collabtbl">
                  <thead>
                    <tr>
                      <th>UserID</th>
                      <th>UserName</th>
                    </tr>
                  </thead>
                  <tbody>{
                    _.map(this.state.usrswithsels, (u) => { 
                      let grpmemsel = <input type="checkbox" data-selkey={u.name} checked={!!u.selected} onChange={this.checkUncheck}/>;
                      if(this.props.amILeader) {
                        return (<tr key={u.name}><td>{u.name} {grpmemsel}</td><td>{u.uidNumber}</td></tr>)
                      } else {
                        return (<tr key={u.name}><td>{u.name}</td><td>{u.uidNumber}</td></tr>);
                      }
                      
                    })
                  }
                  </tbody>
                </table>
              </div>
            </Col>
          </Row>
        </div>
      </div>
    )
  }
}


export default function Groups() {
  let params = useParams(), reponame = params.name, facilityname = params.facility;;
  const { loading, error, data } = useQuery(REPODETAILS, { variables: { reposinput: { name: reponame, facility: facilityname } } });
  const [ toggleGrpMutation] = useMutation(TOGGLE_GROUPMEMBERSHIP_MUTATION);
  const [ newusergrpfn, { newusergrpdata, newusergrploading, newusergrperror }] = useMutation(NEW_USERGROUP_MUTATION);
  const [showAddGroupModal, setShowAddGroupModal] = useState(false);
  const [ toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems ] = useOutletContext();


  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;
  let repodata = data.repos[0], logged_in_user=data.whoami["username"];
  console.log(repodata);
  let leaders = _.get(repodata, "leaders", []), principal = _.get(repodata, "principal"), amILeader = _.includes(leaders, logged_in_user) || principal==logged_in_user;


  let toggleUserMembershipForGroup = function(username, groupname) {
    toggleGrpMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, user: { username: username }, group: { name: groupname } }, refetchQueries: [ REPODETAILS, 'Repos' ], onError: (error) => { console.log("Error when toggling role " + error); } });
  }

  let createNewUserGroup = function(newusergroupname) {
    newusergrpfn({ variables: { reposinput: { name: reponame, facility: facilityname }, grp: { name: newusergroupname, repoid: repodata["Id"], members: [] } }, refetchQueries: [ REPODETAILS, 'Repos' ], onError: (error) => { console.log("Error when creating new user group role " + error); } });
  }

  return (<GroupsTab repodata={repodata} groups={repodata.accessGroupObjs} allUsers={repodata.allUsers} amILeader={amILeader}
    showModal={showAddGroupModal} setShowModal={setShowAddGroupModal} createNewUserGroup={createNewUserGroup}
    onSelDesel={toggleUserMembershipForGroup} reponame={repodata.name}
    toolbaritems={toolbaritems} setToolbaritems={setToolbaritems}
    />);
}
