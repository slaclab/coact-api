import React, { Component, useState } from 'react';
import Button from 'react-bootstrap/Button';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Table from "react-bootstrap/Table";
import Modal from 'react-bootstrap/Modal';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Fade from 'react-bootstrap/Fade';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import { Link, useParams, useOutletContext } from "react-router-dom";
import { useQuery, useLazyQuery, useMutation, gql } from "@apollo/client";
import dayjs from "dayjs";
import dayOfYear from 'dayjs/plugin/dayOfYear';
import Plot from "react-plotly.js";
import { ChargeFactor, TwoPrecFloat, DateTimeDisp } from "./widgets";
import _ from "lodash";

dayjs.extend(dayOfYear);

const REPODETAILS = gql`
query Repos($reposinput: RepoInput, $allocationid: MongoId!){
  repos(filter:$reposinput) {
    name
    facility
    users
    facilityObj {
      name
      computepurchases {
        purchased
        clustername
      }  
    }
    computeAllocation(allocationid: $allocationid) {
      clustername
      start
      end
      percentOfFacility
      userAllocations {
        username
        percent
      }
      usage {
        resourceHours
      }
      perDateUsage {
        date
        resourceHours
      }
      perUserUsage {
        username
        resourceHours
      }
    }
  }
  clusters {
    name
    nodecpucount
    nodecpucountdivisor
    chargefactor
  }
  whoami {
    username
    isAdmin
    isCzar
  }
}
`;

const ALLOCATION_MUTATION = gql`
mutation UpdateUserAllocation($reposinput: RepoInput!, $data: [UserAllocationInput!]!){
  repoUpdateUserAllocation(repo: $reposinput, data: $data){
    name
  }
}
`;

const REPO_COMPUTE_ALLOCATION_REQUEST = gql`
mutation requestRepoComputeAllocation($request: CoactRequestInput!){
  requestRepoComputeAllocation(request: $request){
    Id
  }
}
`;

const APPROVE_REQUEST_MUTATION = gql`
mutation ApproveRequest($Id: String!){
  requestApprove(id: $Id)
}
`;

const REPO_PAST_X_JOBS = gql`
query repoComputeJobs($pastXMins: Int!, $allocationid: MongoId!) {
  repoComputeJobs(pastXMins: $pastXMins, rca: {Id: $allocationid}) {
    startTs
    endTs
    durationMillis
    jobId
    resourceHours
    normalizedResourceHours
    qos
    username
  }
}`;

class User extends React.Component {
  constructor(props) {
    super(props);
    this.computeRemaining = (allocation_percent) => {
      let allocated_compute = _.toNumber(allocation_percent)*this.props.repoallocation/100;
      let remaining_compute = allocated_compute - _.get(this.props.user, "resourceHours", 0);
      let remaining_percent = (remaining_compute/allocated_compute)*100.0;
      return {
        "allocation": _.toNumber(allocation_percent),
        "allocated_compute": allocated_compute,
        "remaining_compute": remaining_compute,
        "remaining_percent": remaining_percent,
        "updt_sts_cls": ""
      }
    }
    this.onUserAllocChangeSuccess = () => {
      console.log("Successfully changed");
      this.setState({"updt_sts_cls": "inplacesuccess"})
    }
    this.onUserAllocChangeError = (error) => {
      console.log("Failed to change user allocation " + error);
      this.setState({"updt_sts_cls": "inplaceerror"})
    }
    this.handleChange = (event) => {
      this.setState({"updt_sts_cls": ""})
      let current_percent = _.get(this.props.user, "allocation.percent", 0);
      if(current_percent == _.toNumber(event.target.value)) {
        console.log("Value has not changed. Skipping updating the DB " + current_percent + " and " + _.toNumber(event.target.value));
        return;
      }
      this.props.onAllocationChange(this.props.user.username, event.target.value, this.onUserAllocChangeSuccess, this.onUserAllocChangeError);
      this.setState(this.computeRemaining(event.target.value));
    }
    this.state = this.computeRemaining(_.get(this.props.user, "allocation.percent", 0));
  }

  render() {
    return (
      <Row data-userid={this.props.user.username}>
        <Col>{this.props.user.username}</Col>
        {/* <Col className={this.state.updt_sts_cls}><input className="usrcmpalc" type="number" defaultValue={this.state.allocation} onBlur={this.handleChange}/>
             <span className="invalid-feedback"></span></Col>
        <Col><TwoPrecFloat value={this.state.allocated_compute}/></Col> */}
        <Col><TwoPrecFloat value={this.props.user.resourceHours}/></Col>
        {/* <Col><TwoPrecFloat value={this.state.remaining_percent}/></Col> */}
      </Row>
    )}
}

class TopTab extends React.Component {
  constructor(props) {
    super(props);
    this.allocatedCompute = props.allocatedCompute;
    this.resourceHours_charged = _.sum(_.map(_.get(this.props.repodata.computeAllocation, "usage", []), "resourceHours"));
    let startdate = dayjs(_.get(props.repodata.computeAllocation, "start")), enddate = dayjs(_.get(props.repodata.computeAllocation, "end"));
    this.allocatedResourceHours = props.allocatedCompute * (enddate.diff(startdate, "days"))*24*props.clusterInfo.nodecpucount;
    console.log(dayjs(this.props.repodata.computeAllocation.end).subtract(dayjs(this.props.repodata.computeAllocation.start), "days"));
    this.available_resourceHours = this.allocatedResourceHours - this.resourceHours_charged;
    this.remaining_percent = (this.available_resourceHours/this.allocatedResourceHours)*100.0;
  }
  render() {
    return (<><Row>
      <Col><label>Current allocation</label></Col>
      <Col><span>{this.allocatedCompute}</span><span className="px-2 fst-italic">{ "(" + this.props.currallocation + "%)"}</span></Col>
      <Col><label>In hours</label></Col>
      <Col><span><TwoPrecFloat value={this.allocatedResourceHours}/></span></Col>
      <Col><label>Hours charged</label></Col>
      <Col><TwoPrecFloat value={this.resourceHours_charged}/></Col>
      <Col><label>Available hours</label></Col>
      <Col><TwoPrecFloat value={this.available_resourceHours}/></Col>
      <Col><label>Remaining %</label></Col>
      <Col><TwoPrecFloat value={this.remaining_percent}/></Col>
      </Row></>
    );
  }
}

class MidChart extends React.Component {
  constructor(props) {
    super(props);
    this.current_allocation = props.allocatedCompute;
    let per_date_usage = _.get(props.repodata.computeAllocation, "perDateUsage", []);
    let startdate = dayjs(_.get(props.repodata.computeAllocation, "start")), enddate = dayjs(_.get(props.repodata.computeAllocation, "end"));
    let per_day_allocation = this.current_allocation/(enddate.diff(startdate, "days"));
    console.log(per_day_allocation);

    this.layout = { showlegend: true, legend: { x: 0.075, xanchor: 'center', y: 0.98, font: { family: 'Optima, Helevetica, Lucida Grande, Lucida Sans, sans-serif', size: 14, color: '#000' } }, autosize: false, width: window.innerWidth, height: 0.4*window.innerHeight, margin: { t: 0, b: -0.1 } };
    let uniform_charge_rate = { x: [], y: [], type: 'scatter', name: "Uniform Charge Rate" }, daily_charge_rate = { x: [], y: [], type: 'scatter', "name": "Hours charged" };
    let daily_usage_by_day = _.keyBy(per_date_usage, (x) => dayjs(x["date"]).dayOfYear()), cuml_daily_usage = 0, today = dayjs();
    for(let i=0, d = startdate; d.isBefore(enddate); d = d.add(1, "days"), i=i+1) {
      uniform_charge_rate.x.push(d.toDate()); uniform_charge_rate.y.push(i*per_day_allocation);
      if(d.isBefore(today)){ daily_charge_rate.x.push(d.toDate()); cuml_daily_usage = cuml_daily_usage + (_.get(daily_usage_by_day, d.dayOfYear() + ".resourceHours", 0)); daily_charge_rate.y.push(cuml_daily_usage); }
    }
    this.chartdata = [uniform_charge_rate, daily_charge_rate];
  }

  render() {
    return (
      <div className="midchart">
        <Plot data={this.chartdata} layout={this.layout} style={{width: "100%", height: "100%"}} />
      </div>
    )
  }
}


class BottomTab extends React.Component {
  constructor(props) {
    super(props);
    this.state = { past_x_jobs:  [] }
    this.current_allocation = props.allocatedCompute;

    const repodata = props.repodata,
      per_user_allocations = _.get(this.props.repodata.computeAllocation, "userAllocations", []),
      per_user_usage = _.get(this.props.repodata.computeAllocation, "perUserUsage", []),
      repo_users = _.get(repodata, "users", []);


    console.log(per_user_usage);
    // Users can come and go.. Collect all the users from the both the repo itself and also from any past jobs
    var users = _.fromPairs(_.map(_.union(_.map(per_user_allocations, "username"), _.map(per_user_usage, "username"), repo_users), u => [ u, { username: u, allocated_compute: 0, remaining_compute: 0, remaining_percent: 100}]));
    _.each(per_user_allocations, function(v,k){ users[v["username"]]["allocation"] = _.cloneDeep(v) });
    _.each(per_user_usage, function(pu){ users[pu["username"]]["resourceHours"] = pu["resourceHours"] });
    console.log(users);

    this.users = users;
  }

  render() {
    let getPastXJobs = (mins) => {
      console.log("Fetching job data from server");
      this.props.getPastXJobs({
        variables: { pastXMins: mins, allocationid: this.props.repoComputeAllocationId },
        onCompleted: (data) => {
          let jobs = _.get(data, "repoComputeJobs", []);
          console.log(jobs);
          this.setState({ past_x_jobs : jobs })
        }
      })
    }

    let tabselected = (eventkey) => { 
      console.log(eventkey);
      if(eventkey == "users") {
        this.setState({ past_x_jobs : [] });
      } else if(eventkey == "past_5") {
        getPastXJobs(5);
      } else if(eventkey == "past_15") {
        getPastXJobs(15);
      } else if(eventkey == "past_60") {
        getPastXJobs(60);
      } else if(eventkey == "past_180") {
        getPastXJobs(180);
      }      
    }

    let pastXTable = () => { 
      return (
        <Table striped bordered hover>
          <thead>
            <tr><th>JobId</th><th>QOS</th><th>ResourceHours</th><th>Normalized ResourceHours</th><th>Start time</th><th>End Time</th><th>Duration (in s)</th></tr>
          </thead>
          <tbody>
            {_.map(this.state.past_x_jobs, (job) => <tr key={job.jobId}><td>{job.jobId}</td><td>{job.qos}</td><td><TwoPrecFloat value={job.resourceHours}/></td><td><TwoPrecFloat value={job.normalizedResourceHours}/></td><td><DateTimeDisp value={job.startTs}/></td><td><DateTimeDisp value={job.endTs}/></td><td><TwoPrecFloat value={job.durationMillis/1000}/></td></tr>)}
          </tbody>
        </Table>
      )
    }

    return (
      <div className="btmtbl">
        <Tabs defaultActiveKey="users"  onSelect={(eventkey) => tabselected(eventkey)}>
          <Tab eventKey="users" title="Users">
            <Row className="hdr">
              <Col>Username</Col>
              {/* <Col>Allocation (% of repo)</Col>
              <Col>Allocated hours</Col> */}
              <Col>Used hours</Col>
              {/* <Col>Remaining hours</Col> */}
            </Row>
            {_.map(_.sortBy(this.users, "username"), (user, k) => ( <User key={user.username}  user={user} repoallocation={this.current_allocation} onAllocationChange={this.props.onAllocationChange}/> ))}
          </Tab>
          <Tab eventKey="past_5" title="Past 5">
            {pastXTable()}
          </Tab>
          <Tab eventKey="past_15" title="Past 15">
            {pastXTable()}
          </Tab>
          <Tab eventKey="past_60" title="Past 60">
            {pastXTable()}
          </Tab>
          <Tab eventKey="past_180" title="Past 180">
            {pastXTable()}
          </Tab>
        </Tabs>
      </div>
    );
    }
}

class ChangeAllocationModal extends Component {
  constructor(props) {
    super(props);
    this.state = { allocationRequest: this.props.currallocation, notes: "", modalError: false, modalErrorMessage: "" }
    this.handleClose = () => { this.props.setShow(false); }
    this.setAllocationRequest = (event) => { this.setState({ allocationRequest: event.target.value }) }
    this.setnotes = (event) => { this.setState({ notes: event.target.value }) }
    this.changeAllocationRequest = () => {
      console.log(this.state.allocationRequest);
      this.props.requestChangeAllocation(this.state.allocationRequest, this.state.notes, () => { this.props.setShow(false); }, (errmsg) => { this.setState({modalError: true, modalErrorMessage: errmsg})} );
    }
  }
  render() {
    return (
      <Modal backdrop="static" show={this.props.show} onHide={this.handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Change compute allocation for {this.props.reponame} on cluster {this.props.clustername}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="mb-3">
            <p>A compute allocation is specified as a percentage of the facility's allocation.</p>
            <p>The facility <b className="em">{this.props.facilityname}</b> has purchased <b className="em">{this.props.facilityPurchased}</b> on the <b className="em">{this.props.clustername}</b> cluster</p>
            <InputGroup hasValidation>
              <InputGroup.Text>Current Percent:</InputGroup.Text>
              <Form.Control type="number" value={this.state.allocationRequest} defaultValue={this.state.allocationRequest} onChange={this.setAllocationRequest} isInvalid={this.state.modalError}/>
              <Form.Control.Feedback type="invalid">{this.state.modalErrorMessage}</Form.Control.Feedback>
            </InputGroup>
            <Form.Text>Any additional comments</Form.Text>
            <Row className="mb-3">
              <InputGroup>
                <Form.Control as="textarea" rows={3} value={this.state.notes} placeholder="Please enter any additional comments" onChange={this.setnotes}/>
              </InputGroup>
            </Row>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="light" onClick={this.handleClose}>
            Close
          </Button>
          <Button variant="primary" onClick={this.changeAllocationRequest}>
            Submit request
          </Button>
        </Modal.Footer>
      </Modal>
    )
  }
}

class ComputeTab extends React.Component {
  constructor(props) {
    super(props);
  }

  componentDidMount() {
    this.props.setToolbaritems(oldItems => [...oldItems, ["Request more compute", this.props.setAllocMdlShow]]);
  }

  componentWillUnmount() {
    this.props.setToolbaritems(oldItems => _.filter(oldItems, (x) => { return x[0] != "Request more compute" }));
  }

  render() {
    return (<div className="container-fluid text-left tabcontainer">
      <ChangeAllocationModal show={this.props.allocMdlShow} setShow={this.props.setAllocMdlShow} reponame={this.props.repodata.name} clustername={this.props.repodata.computeAllocation.clustername} currallocation={this.props.repodata.computeAllocation.percentOfFacility} facilityPurchased={this.props.facilityPurchased} requestChangeAllocation={this.props.requestChangeAllocation}/>
      <Row>
        <Col className="text-left"><div className="brdcrmb"><Link to={"../compute"}>Compute </Link> / {this.props.repodata.name} - {this.props.repodata.computeAllocation.clustername}</div></Col>
        <Col className="text-center"><div className="sectiontitle">Resource usage for repo <span className="ref">{this.props.repodata.name}</span> on the <span className="ref">{this.props.repodata.computeAllocation.clustername}</span> cluster</div></Col>
        <Col></Col>
      </Row>
      <TopTab repodata={this.props.repodata} allocatedCompute={this.props.allocatedCompute} clusterInfo={this.props.clusterInfo} currallocation={this.props.repodata.computeAllocation.percentOfFacility} isAdminOrCzar={this.props.isAdminOrCzar} />
      <MidChart repodata={this.props.repodata} allocatedCompute={this.props.allocatedCompute}/>
      <BottomTab repodata={this.props.repodata} onAllocationChange={this.props.onAllocationChange} allocatedCompute={this.props.allocatedCompute} repoComputeAllocationId={this.props.repoComputeAllocationId} getPastXJobs={this.props.getPastXJobs}/>
    </div>)
  }
}

export default function Compute() {
  let params = useParams(), reponame = params.name, facilityname = params.facility, allocationid = params.allocationid, datayear = dayjs().year();
  const { loading, error, data } = useQuery(REPODETAILS, { variables: { reposinput: { name: reponame, facility: facilityname }, allocationid: allocationid } });
  const [ repoUpdateUserAllocation, { allocdata, allocloading, allocerror }] = useMutation(ALLOCATION_MUTATION);
  const [ repocmpallocfn, { repocmpallocdata, repocmpallocloading, repocmpallocerror }] = useMutation(REPO_COMPUTE_ALLOCATION_REQUEST);
  const [ approveRequest, { arD, arL, arE } ] = useMutation(APPROVE_REQUEST_MUTATION);
  const [ getPastXJobs ] = useLazyQuery(REPO_PAST_X_JOBS);
  const [ allocMdlShow, setAllocMdlShow] = useState(false);
  const [ toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems ] = useOutletContext();


  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;
  let repodata = data.repos[0];

  console.log(repodata);
  let facilityPurchased = _.get(_.find(repodata["facilityObj"]["computepurchases"], ["clustername", repodata["computeAllocation"]["clustername"]]), "purchased", 0.0);
  let totalAllocatedCompute = _.get(repodata, "computeAllocation.percentOfFacility", 0.0)*facilityPurchased/100.0;
  let clusterInfo = _.keyBy(data.clusters, "name")[repodata["computeAllocation"]["clustername"]];

  const isAdminOrCzar = data.whoami.isAdmin || data.whoami.isCzar;  

  let changeAllocation = (username, allocation_percent, callWhenDone, callOnError) => {
    console.log("Changing allocation for user " + username + " to " + _.toNumber(allocation_percent));
    repoUpdateUserAllocation({ variables: { reposinput: { name: reponame, facility: facilityname }, data: [ {
      allocationid: allocationid,
      username: username,
      percent: _.toNumber(allocation_percent)
    } ] }, onCompleted: callWhenDone, onError: (error) => { callOnError(error.message)} });
  }

  let requestChangeAllocation = function(newalloc, notes, callWhenDone, callOnError) {
    console.log("Adding a request to change allocation to " + newalloc);
    repocmpallocfn({ variables: { request: { reqtype: "RepoComputeAllocation", reponame: reponame, facilityname: repodata.facility, clustername: repodata.computeAllocation.clustername, start: repodata.computeAllocation.start, percentOfFacility: _.toNumber(newalloc), notes: notes }},
    onCompleted: callWhenDone, onError: (error) => { callOnError(error.message)}});
  }

  return (<ComputeTab repodata={repodata} facilityPurchased={facilityPurchased} allocatedCompute={totalAllocatedCompute} 
    clusterInfo={clusterInfo} onAllocationChange={changeAllocation}
    allocMdlShow={allocMdlShow} setAllocMdlShow={setAllocMdlShow} requestChangeAllocation={requestChangeAllocation}
    toolbaritems={toolbaritems} setToolbaritems={setToolbaritems} isAdminOrCzar={isAdminOrCzar} getPastXJobs={getPastXJobs} repoComputeAllocationId={allocationid}
    />);
}
