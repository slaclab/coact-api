import _ from "lodash";
import { useParams, useOutletContext } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import Button from 'react-bootstrap/Button';
import InputGroup from 'react-bootstrap/InputGroup';
import Alert from 'react-bootstrap/Alert';
import { StringListManager } from "./widgets";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faEdit, faTrash } from '@fortawesome/free-solid-svg-icons'


const REPOFEATURES = gql`
query repoFeatures($repo: String!, $facility: String!){
  repo(filter: { name: $repo, facility: $facility }) {
    name
    facility
    features {
      name
      state
      options
    }
  }
  whoami {
    username
    isAdmin
    isCzar
  }
}`;

const ADD_FEATURE_MUTATION = gql`
mutation repoAddNewFeature($reposinput: RepoInput!, $feature: RepoFeatureInput!){
  repoAddNewFeature(repo: $reposinput, feature: $feature){
    name
    features {
      name
      state
      options
    }
  }
}
`;

const DELETE_FEATURE_MUTATION = gql`
mutation repoDeleteFeature($reposinput: RepoInput!, $featurename: String!){
  repoDeleteFeature(repo: $reposinput, featurename: $featurename){
    name
    features {
      name
      state
      options
    }
  }
}
`;

const UPDATE_FEATURE_MUTATION = gql`
mutation repoUpdateFeature($reposinput: RepoInput!, $feature: RepoFeatureInput!){
  repoUpdateFeature(repo: $reposinput, feature: $feature){
    name
    features {
      name
      state
      options
    }
  }
}
`;






class AddEditNewFeature extends Component {
  constructor(props) {
    super(props);
    this.state = { 
      isEditing: !_.isEmpty(this.props.featureBeingEdited),
      featname: this.props.featureBeingEdited, 
      options: _.isEmpty(this.props.featureBeingEdited) ? [] : _.find(this.props.repo.features, ["name", this.props.featureBeingEdited])["options"],
      validationError: false, 
      validationErrorMsg: "" 
    };

    this.copyState = () => { 
      this.setState({
        isEditing: !_.isEmpty(this.props.featureBeingEdited),
        featname: this.props.featureBeingEdited, 
        options: _.isEmpty(this.props.featureBeingEdited) ? [] : _.find(this.props.repo.features, ["name", this.props.featureBeingEdited])["options"],
        validationError: false, 
        validationErrorMsg: ""   
      })
    }


    this.handleClose = () => { props.setShow(false); }
    this.setName = (ev) => { 
      const ftname = ev.target.value;
      this.setState({ featname: ftname })
    }
    this.addOption = (newitem) => { 
      this.setState({options: _.concat(this.state.options, [newitem])})
    }
    this.removeOption = (item) => { 
      this.setState({options: _.without(this.state.options, item)})
    }
    this.addEditFeature = () => { 
      if(_.isNil(this.state.featname) || _.isEmpty(this.state.featname) || !/^[a-z0-9]+$/i.test(this.state.featname)) {
        this.setState({ validationError: true, validationErrorMsg: "Please enter a valid name for the feature" });
        return;
      }

      if(!this.state.isEditing && !_.isNil(_.find(props.currentFeatures, ["name", this.state.featname]))) {
        this.setState({ validationError: true, validationErrorMsg: `The feature ${this.state.featname} is already defined` });
        return;
      }
      if(this.state.isEditing) {
        props.updateFeature({name: this.state.featname, state: true, options: this.state.options}, () => { props.setShow(false) }, (errorMsg) => { this.setState({ validationError: true, validationErrorMsg: errorMsg }); } )
      } else {
        props.addNewFeature({name: this.state.featname, state: true, options: this.state.options}, () => { props.setShow(false) }, (errorMsg) => { this.setState({ validationError: true, validationErrorMsg: errorMsg }); } )
      }
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose} onShow={this.copyState}>
        <Modal.Header closeButton>
          <Modal.Title>{ this.state.isEditing ? "Edit feature " + this.props.featureBeingEdited : "Add New Feature" }</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className={ this.state.isEditing ? "d-none": "" }>
              <Form.Label className="fw-bold">Name:</Form.Label>
              <InputGroup hasValidation>
                <Form.Control isInvalid={this.state.validationError} onChange={this.setName} value={this.state.featname}></Form.Control>
                <Form.Control.Feedback type="invalid">{this.state.validationErrorMsg}</Form.Control.Feedback>
              </InputGroup>
            </Form.Group>
            <Form.Group className="mt-2">
              <Form.Label className="fw-bold">Options:</Form.Label>
              <StringListManager label={"Options"} addLabel={"Add option"} items={this.state.options} addItem={this.addOption} removeItem={this.removeOption}/>
            </Form.Group>
            
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.addEditFeature}>
            { this.state.isEditing ? "Save": "Add" }
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}


class RepoFeaturesTable extends Component {
  constructor(props) {
    super(props);
    this.state = { featureBeingEdited: "", showModal: false, isError:false, errorMsg: "" }

    this.showError = (errormsg) => { 
      this.setState({isError:true, errorMsg: errormsg});
    }

    this.setShowModal = (show) => { 
      this.setState({showModal: show})
    }

    this.deleteFeature = function(ftname) {
      this.props.deleteFeature(ftname, () => {}, this.showError);
    }

    this.editFeature = function(ftname) {
      this.setState({featureBeingEdited: ftname, showModal: true});
    }


    this.toggleFeature = function(ftname) {
      console.log(`Toggling feature ${ftname}`);
      let fcopy = _.map(this.props.repo.features, (ft) => { return _.fromPairs(_.filter(_.map(ft, (v,k) => { return [ k, v ] }), (x) => _.includes(["name", "state", "options"], x[0]))) })
      let theFeature = _.find(fcopy, ["name", ftname]);
      _.set(theFeature, "state", !_.get(theFeature, "state", false));
      this.props.updateFeature(theFeature, () => {}, this.showError);
    }
  }

  componentDidMount() {
    if(this.props.isAdmin) {
      this.props.setToolbaritems(oldItems => [...oldItems, ["Add new feature", (state) => { this.setState({featureBeingEdited: "", showModal: true});; this.setShowModal(state)}]]);
    }
  }

  componentWillUnmount() {
    this.props.setToolbaritems(oldItems => _.filter(oldItems, (x) => { return x[0] != "Add new feature" }));
  }

  render() {
    return (
      <>
      <Alert show={this.state.isError} variant="danger" dismissible onClose={() => this.setState({isError:false, errorMsg: ""})}>
        <Alert.Heading>Error</Alert.Heading>
          <p>{this.state.errorMsg}</p>
      </Alert> 
      <h5 className="text-center">Features for repo <span className="text-warning">{this.props.repo.name}</span> in facility <span className="text-warning">{this.props.repo.facility}</span></h5>
      {
        _.map(this.props.repo.features, (ft) => { 
          return (
            <Card className="m-2" key={ft["name"]}>
              <Card.Body>
                <Card.Title>
                  {ft["name"]}
                  { this.props.isAdmin ? (
                  <span className="float-end text-primary fs-6">
                    <span className="px-1" onClick={() => this.editFeature(ft["name"])}><FontAwesomeIcon icon={faEdit}/></span>
                    <span className="px-1" onClick={() => this.deleteFeature(ft["name"])}><FontAwesomeIcon icon={faTrash}/></span>
                  </span>
                  ) : "" }
                </Card.Title>
                <Card.Text as={"div"}>
                  <Row>
                    <Col xs={2}>
                      <Form.Check type="switch" id={ft["name"]} defaultChecked={ft.state} disabled={this.props.isAdmin ? false : true } onChange={(ev) => { this.toggleFeature(ft["name"], ev) }}/>
                    </Col>
                    <Col>
                      <ul>
                      {_.map(_.get(ft, "options", []), (o) => ( <li key={o}>{o}</li> ))}
                      </ul>
                    </Col>
                  </Row>                  
                </Card.Text>
              </Card.Body>
            </Card> 
          );
        })
      }
      <AddEditNewFeature repo={this.props.repo} show={this.state.showModal} setShow={this.setShowModal} 
        featureBeingEdited={this.state.featureBeingEdited} currentFeatures={this.props.repo.features} 
        addNewFeature={this.props.addNewFeature} updateFeature={this.props.updateFeature}/>
      </>
     )
  }
}

export default function RepoFeatures() {
  let params = useParams(), reponame = params.name, facilityname = params.facility;
  const { loading, error, data } = useQuery(REPOFEATURES, { variables: { repo: reponame, facility: facilityname } }, { fetchPolicy: 'no-cache', nextFetchPolicy: 'no-cache'});
  const [ addFeatureMutation ] = useMutation(ADD_FEATURE_MUTATION);
  const [ deleteFeatureMutation ] = useMutation(DELETE_FEATURE_MUTATION);
  const [ updateFeatureMutation ] = useMutation(UPDATE_FEATURE_MUTATION);
  const [ toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems ] = useOutletContext();


  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  console.log(data);

  const isAdmin = data.whoami.isAdmin;
  const isAdminOrCzar = data.whoami.isAdmin || data.whoami.isCzar;  

  const addNewFeature = (feature, onSuccess, onError) => {
    addFeatureMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, feature: feature }, 
      refetchQueries: [ REPOFEATURES ], 
      onCompleted: onSuccess, 
      onError: (error) => { onError(error.message) }})
  };

  const deleteFeature = (featurename, onSuccess, onError) => { 
    deleteFeatureMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, featurename: featurename }, 
      refetchQueries: [ REPOFEATURES ], 
      onCompleted: onSuccess, 
      onError: (error) => { onError(error.message) }})
  }

  const updateFeature = (feature, onSuccess, onError) => {
    updateFeatureMutation({ variables: { reposinput: { name: reponame, facility: facilityname }, feature: feature }, 
      refetchQueries: [ REPOFEATURES ], 
      onCompleted: onSuccess, 
      onError: (error) => { onError(error.message) }})
  };


  return (
    <>
    <RepoFeaturesTable isAdmin={isAdmin} isAdminOrCzar={isAdminOrCzar} repo={data.repo}
      toolbaritems={toolbaritems} setToolbaritems={setToolbaritems}
      addNewFeature={addNewFeature} deleteFeature={deleteFeature} updateFeature={updateFeature}
    />
    </>
  );
}
