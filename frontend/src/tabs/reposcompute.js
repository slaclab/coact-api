import _ from "lodash";
import { NavLink, useOutletContext } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faEdit } from '@fortawesome/free-solid-svg-icons'
import { TwoPrecFloat, DateDisp, TwoPrecPercent } from "./widgets";
import Modal from 'react-bootstrap/Modal';
import ModalHeader from 'react-bootstrap/ModalHeader';
import ModalTitle from 'react-bootstrap/ModalTitle';
import ModalBody from 'react-bootstrap/ModalBody';
import ModalFooter from 'react-bootstrap/ModalFooter';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Tooltip from 'react-bootstrap/Tooltip';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Popover from 'react-bootstrap/Popover';
import Table from 'react-bootstrap/Table';

const REPOS = gql`
query myRepos($skipQoses: [String!]!){
  myRepos{
    Id
    name
    facility
    principal
    currentComputeAllocations {
      Id
      clustername
      clusterNodeCPUCount
      start
      end
      percentOfFacility
      allocated
      burstPercentOfFacility
      burstAllocated
      usage {
        resourceHours
      }      
    }
  }
  whoami {
    username
    isAdmin
    isCzar
  }
  facilities {
    name
    computepurchases {
      purchased
      clustername
    }
  }
  clusters {
    name
    nodecpucount
  }
  clusterPurchases {
    clustername
    totalpurchased
  }    
	pastHour:repoRecentComputeUsage(pastMinutes: 60, skipQoses: $skipQoses) {
    name
    clustername
    facility
    percentUsed
    resourceHours
  }  
  pastDay:repoRecentComputeUsage(pastMinutes: 1440, skipQoses: $skipQoses) {
    name
    clustername
    facility
    percentUsed
    resourceHours
  }  
  pastWeek:repoRecentComputeUsage(pastMinutes: 10080, skipQoses: $skipQoses) {
    name
    clustername
    facility
    percentUsed
    resourceHours
  }  
  pastMonth:repoRecentComputeUsage(pastMinutes: 44640, skipQoses: $skipQoses) {
    name
    clustername
    facility
    percentUsed
    resourceHours
  }  
}`;

const ALLOCATION_REQUEST = gql`
mutation requestRepoComputeAllocation($request: CoactRequestInput!){
  requestRepoComputeAllocation(request: $request){
    Id
  }
}
`;

const APPROVE_REQUEST_MUTATION = gql`
mutation requestApprove($Id: String!){
  requestApprove(id: $Id)
}
`;

class AddComputeAllocation extends Component {
  constructor(props) {
    super(props);
    this.state = { currentCluster: "", facilityPurchased: 0.0, currentAllocation: 0, currentBurstAllocation: 0, showalloc: false, zeroalloc: false }
    this.setCluster = (event) => { 
      let clustername = event.target.value;
      let facilityData = _.find(this.props.facilities, ["name", this.props.facilityname]);
      let facilityPurchased = _.get(_.find(_.get(facilityData, "computepurchases", {}), ["clustername", clustername]), "purchased", 0.0);
      let fixedzero = facilityPurchased <= 0 || this.props.reponame == "default";
      this.setState({currentCluster: clustername, facilityPurchased: facilityPurchased, showalloc: !fixedzero, zeroalloc: fixedzero, currentAllocation: fixedzero ? 0 : 20}) 
    }
    this.setAllocation = (event) => { this.setState({currentAllocation: event.target.value}) }
    this.setBurstAllocation = (event) => { this.setState({currentBurstAllocation: event.target.value}) }
    this.hideModal = () => { 
      this.setState({currentCluster: "", facilityPurchased: 0.0, currentAllocation: 0, showalloc: false, zeroalloc: false});
      this.props.hideModal();
    }
  }

  render() {
    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.hideModal()}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Allocate some compute for the repo <b className="em">{this.props.reponame}</b> on a new cluster</ModalTitle>
        </ModalHeader>
        <ModalBody>
        <InputGroup>
            <InputGroup.Text>Choose a cluster:</InputGroup.Text>
            <Form.Select name="cluster" value={this.state.currentCluster} onChange={this.setCluster}>
                <option value="">Please choose a cluster</option>
                { _.map(this.props.clustersunallocated, (s) => { return (<option key={s} value={s}>{s}</option>)}) }
            </Form.Select>
          </InputGroup>
          <div className={this.state.showalloc ? "py-2" : "d-none"}>
            <p>A compute allocation is specified as a percentage of the facility's allocation.</p>
            <p>The facility <b className="em">{this.props.facilityname}</b> has purchased <b className="em">{this.state.facilityPurchased}</b> on the <b className="em">{this.props.clustername}</b> cluster</p>
            <InputGroup hasValidation>
              <InputGroup.Text>Current Percent:</InputGroup.Text>
              <Form.Control type="number" onChange={this.setAllocation} isInvalid={this.props.isError} value={this.state.currentAllocation}/>
              <Form.Control.Feedback type="invalid">{this.props.errorMessage}</Form.Control.Feedback>
            </InputGroup>
          </div>
          <div className={this.state.zeroalloc ? "py-2" : "d-none"}>
            <p className={this.state.facilityPurchased <= 0 ? "" : "d-none"}>The facility <b className="em">{this.props.facilityname}</b> has not purchased any resources on the <b className="em">{this.state.currentCluster}</b> cluster.</p>
            <p>We only allow an allocation of 0% in this case. This implies that only pre-emptable jobs are allowed on this cluster for this repo.</p>
            <InputGroup>
                <InputGroup.Text>Current Percent:</InputGroup.Text>
                <Form.Control type="number" onBlur={this.setAllocation} isInvalid={this.props.isError} defaultValue={this.state.currentAllocation} readOnly/>
            </InputGroup>
          </div>
          <div className={"d-none"}>
            <p>One can also specify the max fraction of the facility's resources that can be at any instant in time as a cap on burst usage.
            </p>
            <InputGroup hasValidation>
              <InputGroup.Text>Current Burst Percent:</InputGroup.Text>
              <Form.Control type="number" onBlur={this.setBurstAllocation} isInvalid={this.props.isError} defaultValue={this.props.currentBurstAllocation}/>
              <Form.Control.Feedback type="invalid">{this.props.errorMessage}</Form.Control.Feedback>
            </InputGroup>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.hideModal()}}>
            Close
          </Button>
          <Button onClick={() => { this.props.applyNewAllocation(this.state.currentCluster, this.state.currentAllocation, this.state.currentBurstAllocation) }}>
            Done
          </Button>
        </ModalFooter>
      </Modal>
    );
  }
}

class UpdateComputeAllocation extends Component {
  constructor(props) {
    super(props);
    this.state = { currentAllocation: props.currentAllocation, currentBurstAllocation: props.currentBurstAllocation ?? 0, changed: false }
    this.setAllocation = (event) => { this.setState({currentAllocation: event.target.value, changed: true}) }
    this.setBurstAllocation = (event) => { this.setState({currentBurstAllocation: event.target.value, changed: true}) }
    this.hideModal = () => { 
      this.setState({currentAllocation: 0, currentBurstAllocation: 0, changed: false});
      this.props.hideModal();
    }
  }

  render() {
    const fixedzero = this.props.facilityPurchased <= 0 || this.props.reponame == "default";
    const showalloc = !fixedzero, zeroalloc = fixedzero;

    return (
      <Modal backdrop="static" show={this.props.showModal} onHide={() => {this.hideModal()}}>
        <ModalHeader closeButton={true}>
          <ModalTitle>Update the compute allocation for the repo <b className="em">{this.props.reponame}</b> on the cluster <b className="em">{this.props.clustername}</b></ModalTitle>
        </ModalHeader>
        <ModalBody>
          <div className={showalloc ? "py-2" : "d-none"}>
            <p>A compute allocation is specified as a percentage of the facility's allocation.</p>
            <p>The facility <b className="em">{this.props.facilityname}</b> has purchased <b className="em">{this.props.facilityPurchased}</b> on the <b className="em">{this.props.clustername}</b> cluster</p>
            <InputGroup hasValidation>
              <InputGroup.Text>Current Percent:</InputGroup.Text>
              <Form.Control type="number" onBlur={this.setAllocation} isInvalid={this.props.isError} defaultValue={this.props.currentAllocation}/>
              <Form.Control.Feedback type="invalid">{this.props.errorMessage}</Form.Control.Feedback>
            </InputGroup>
          </div>
          <div className={zeroalloc ? "py-2" : "d-none"}>
            <p className={this.props.facilityPurchased <= 0 ? "" : "d-none"}>The facility <b className="em">{this.props.facilityname}</b> has not purchased any resources on the <b className="em">{this.props.clustername}</b> cluster.</p>
            <p>We only allow an allocation of 0% in this case. This implies that only pre-emptable jobs are allowed on this cluster for this repo.</p>
            <InputGroup>
                <InputGroup.Text>Current Percent:</InputGroup.Text>
                <Form.Control type="number" onBlur={this.setAllocation} isInvalid={this.props.isError} defaultValue={this.state.currentAllocation} readOnly/>
            </InputGroup>
          </div>
          <p className="d-none mt-2">One can also specify the max fraction of the facility's resources that can be at any instant in time as a cap on burst usage.</p>
          <InputGroup className="d-none" hasValidation>
            <InputGroup.Text>Current Burst Percent:</InputGroup.Text>
            <Form.Control type="number" onBlur={this.setBurstAllocation} isInvalid={this.props.isError} defaultValue={this.props.currentBurstAllocation}/>
            <Form.Control.Feedback type="invalid">{this.props.errorMessage}</Form.Control.Feedback>
          </InputGroup>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={() => {this.props.hideModal()}}>
            Close
          </Button>
          <Button onClick={() => { 
            if(!this.state.changed) {
              console.log("Nothing changed; simply hide the modal");
              this.props.hideModal();
              return;
            }
            this.props.applyUpdateAllocation(this.props.clustername, this.state.currentAllocation, this.state.currentBurstAllocation) 
            }}>
            Done
          </Button>
        </ModalFooter>
      </Modal>
    );
  }
}

function ComputeUsage(props) {
  const { periodname, recentusagebycluster, reponame, facilityname, clustername } = props;
  let usage = _.find(_.get(recentusagebycluster, periodname), {name: reponame, facility: facilityname, clustername: clustername}) ?? { percentUsed: 0, resourceHours: 0 };
  let percentusage = usage.percentUsed;
  let fac_percentusage = percentusage;
  let repo_percentusage = fac_percentusage;
  if(percentusage > 0) {
    const facPurchased = _.get(_.keyBy(_.get(_.keyBy(props.facilities, "name"), props.facilityname + ".computepurchases", []), "clustername", {}), props.clustername + ".purchased", 0);
    const repoAllocated = _.get(_.keyBy(_.get(props.repo, "currentComputeAllocations", []), "clustername"), props.clustername + ".allocated", 0);
    repo_percentusage = percentusage * (facPurchased/repoAllocated);
    if(props.showAsPercentOfRepo) {
      percentusage =  repo_percentusage;
    }  
  }

  return(
    <OverlayTrigger placement={"auto"} overlay={<Popover id="repocompute-popover">
      <Popover.Header as="h3">Compute Usage of <span className={"em"}>{props.reponame}</span> in <span className={"em"}>{props.clustername}</span></Popover.Header>
      <Popover.Body className="striped \">
        <Table striped bordered><tbody>
          <tr><th>Purchased</th><td><TwoPrecFloat value={props.facilityPurchased} onzero={"0"}/> nodes</td></tr>
          <tr><th>Allocated</th><td><TwoPrecFloat value={props.repoAllocation} onzero={"0"}/> nodes</td></tr>
          <tr><th>CPUs per node</th><td><TwoPrecFloat value={props.clusterNodeCPUCount} onzero={"0"}/></td></tr>
          <tr><th>Resource-hours available to the facility per hour</th><td>
            <TwoPrecFloat value={props.facilityPurchased} onzero={"0"}/>
            <b> * </b>
            <TwoPrecFloat value={props.clusterNodeCPUCount} onzero={"0"}/>
          </td></tr>
          <tr><th className="text-center"><span>{`\u21AA `}</span></th><td><TwoPrecFloat value={props.facilityPurchased*props.clusterNodeCPUCount} onzero={"0"}/> per hour</td></tr>
          <tr><th>Resource-hours available to the facility in this time period</th><td><TwoPrecFloat value={props.facilityPurchased*props.clusterNodeCPUCount*props.numHours} onzero={"0"}/></td></tr>
          <tr><th>Resource-hours available to the repo in this time period</th><td><TwoPrecFloat value={props.repoAllocation*props.clusterNodeCPUCount*props.numHours} onzero={"0"}/></td></tr>
          <tr><th>Resource-hours used in this time period</th><td><TwoPrecFloat value={usage.resourceHours} onzero={"0"}/></td></tr>
          <tr><th>Fractional usage of facility</th><td><TwoPrecFloat value={fac_percentusage} onzero={"0"}/>%</td></tr>
          <tr><th>Fractional usage of repo</th><td><TwoPrecFloat value={repo_percentusage} onzero={"0"}/>%</td></tr>
        </tbody></Table>
      </Popover.Body>
    </Popover>}>
      {usage.percentUsed <= 0 ? (<span></span>) : (<span>{percentusage.toFixed(2) + "%"}</span>)}
    </OverlayTrigger>  
  );
}

class ReposRows extends Component {
  constructor(props) {
    super(props);
    this.reponame = props.repo.name;
    this.facility = props.repo.facility;
    this.facilityData = _.find(this.props.facilities, ["name", props.repo.facility]);
    this.twoPrec = function(flt) {
      if(_.isNil(flt)) return "N/A";
      if(flt > 99999998) return "Inf";
      if(flt == 0) return "";
      return (flt).toFixed(2);
    }
  }
  render() {
    var first = true;
    let cas = _.sortBy(_.get(this.props.repo, "currentComputeAllocations", [{}]), "clustername");
    if(cas.length == 0) { cas = [{"clustername": "N/A"}] };
    if(this.props.hideUnused) {
      cas = _.reject(cas, (a) => {
        let lastMonthsUsedHours = this.props.lastMonthsUsages.getUsage(this.props.repo.facility, this.props.repo.name, a.clustername);
        return lastMonthsUsedHours <= 0;
      } )
    }
    let rows = cas.length;
    let trs = _.map(cas, (a) => {
      const clustersPurchased = _.map(_.get(this.facilityData, "computepurchases", []), "clustername");
      const clustersAllocated  = _.map(_.get(this.props.repo, "currentComputeAllocations", []), "clustername");
      const unAllocatedClusters = _.difference(clustersPurchased, clustersAllocated);
      let facilityPurchased = _.get(_.find(this.facilityData.computepurchases, ["clustername", a.clustername]), "purchased", 0.0);
      let percentoffacility = _.get(a, "percentOfFacility", 0.0);
      let totalAllocatedCompute = _.get(a, "allocated", 0.0);
      if(totalAllocatedCompute == 0 && facilityPurchased != 0 && percentoffacility != 0) {
        totalAllocatedCompute = facilityPurchased*percentoffacility/100.0;
      }
      let clusterNodeCPUCount = _.get(a, "clusterNodeCPUCount", 0.0);
      
      let totalUsedHours = _.sum(_.map(_.get(a, "usage", []), "resourceHours"));
      
      let lastMonthsUsedHours = this.props.lastMonthsUsages.getUsage(this.props.repo.facility, this.props.repo.name, a.clustername);
      let lastMonthsUsedPercent = lastMonthsUsedHours/(31.0*totalAllocatedCompute*24)*100;

      let showPlusButton = this.props.canEditAllocations && unAllocatedClusters.length > 0;
      let showEditButton = this.props.isAdmin || (this.props.canEditAllocations && this.reponame != "default");

      if(first) {
        first = false;
        return (
          <tr key={this.facility+this.reponame+a.clustername} data-name={this.reponame} className="text-start px-2 reporow">
            <td rowSpan={rows} className="vmid">{this.reponame} {showPlusButton ? <span className="float-end"><span className="px-2 text-warning" title="Allocate compute on a new cluster" onClick={() => { this.props.showAddModal(this.props.repo, facilityPurchased) }}><FontAwesomeIcon icon={faPlus}/></span></span> : <span></span>}</td>
            <td rowSpan={rows} className="vmid">{this.props.repo.facility}</td>
            <td rowSpan={rows} className="vmid">{this.props.repo.principal}</td>
            <td>{a.clustername == "N/A" ? "None" : <NavLink to={"/repos/compute/"+this.props.repo.facility+"/"+this.reponame+"/allocation/"+a.Id} key={this.reponame} title={"Node CPU count=" + clusterNodeCPUCount}>{a.clustername}</NavLink>}</td>
            <td className="text-end"><CompAllocDetails facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername}><span>{ percentoffacility + "%"}</span></CompAllocDetails> {showEditButton && a.clustername != "N/A" ? <span className="float-end"><span className="px-2 text-warning" title="Edit allocated amount" onClick={() => { this.props.showUpdateModal(this.props.repo, a, facilityPurchased) }}><FontAwesomeIcon icon={faEdit}/></span></span> : <span></span>}</td>
            <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={1} periodname={"pastHour"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
            <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24} periodname={"pastDay"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
            <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24*7} periodname={"pastWeek"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
            <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24*31} periodname={"pastMonth"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
            <td className="text-end"><TwoPrecFloat value={totalUsedHours}/></td>
            <td><DateDisp value={a.start}/></td>
            <td><DateDisp value={a.end}/></td>
          </tr>)
        } else {
          return (
            <tr key={this.facility+this.reponame+a.clustername} data-name={this.reponame} className="text-start px-2">
              <td><NavLink to={"/repos/compute/"+this.props.repo.facility+"/"+this.reponame+"/allocation/"+a.Id} key={this.reponame} title={"Node CPU count=" + clusterNodeCPUCount}>{a.clustername}</NavLink></td>
              <td className="text-end"><CompAllocDetails facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} title={this.twoPrec(totalAllocatedCompute) + " nodes"} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} ><span>{ percentoffacility + "%"}</span></CompAllocDetails> {showEditButton ? <span className="float-end"><span className="px-2 text-warning" title="Edit allocated amount" onClick={() => { this.props.showUpdateModal(this.props.repo, a, facilityPurchased) }}><FontAwesomeIcon icon={faEdit}/></span></span> : <span></span>}</td>
              <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={1} periodname={"pastHour"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
              <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24} periodname={"pastDay"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
              <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24*7} periodname={"pastWeek"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
              <td className="text-end"><span><ComputeUsage facilityPurchased={facilityPurchased} repoAllocation={totalAllocatedCompute} clusterNodeCPUCount={clusterNodeCPUCount} numHours={24*31} periodname={"pastMonth"} recentusagebycluster={this.props.recentusagebycluster} reponame={this.reponame} facilityname={this.facility} clustername={a.clustername} showAsPercentOfRepo={this.props.showAsPercentOfRepo} repo={this.props.repo} facilities={this.props.facilities}/></span></td>
              <td className="text-end"><TwoPrecFloat value={totalUsedHours}/></td>
              <td><DateDisp value={a.start}/></td>
              <td><DateDisp value={a.end}/></td>
            </tr>)
        }
    });
    return ( <React.Fragment>{trs}</React.Fragment> )
  }
}

const CompAllocDetails = ({ children, facilityPurchased, clusterNodeCPUCount, repoAllocation, reponame, clustername }) => (
  <OverlayTrigger placement={"auto"} overlay={<Popover id="repocompute-popover">
    <Popover.Header as="h3">Compute Allocation of <span className={"em"}>{reponame}</span> in <span className={"em"}>{clustername}</span></Popover.Header>
    <Popover.Body className="striped \">
      <Table striped bordered><tbody>
        <tr><th>Purchased</th><td><TwoPrecFloat value={facilityPurchased} onzero={"0"}/> nodes</td></tr>
        <tr><th>Allocated</th><td><TwoPrecFloat value={repoAllocation} onzero={"0"}/> nodes</td></tr>
        <tr><th>CPUs per node</th><td><TwoPrecFloat value={clusterNodeCPUCount} onzero={"0"}/></td></tr>
        <tr><th>Resource-hours available to the facility</th><td>
          <TwoPrecFloat value={facilityPurchased} onzero={"0"}/>
          <b> * </b>
          <TwoPrecFloat value={clusterNodeCPUCount} onzero={"0"}/>
        </td></tr>
        <tr><th className="text-center"><span>{`\u21AA `}</span></th><td><TwoPrecFloat value={facilityPurchased*clusterNodeCPUCount} onzero={"0"}/> per hour</td></tr>
        <tr><th>Resource-hours available to the repo </th><td><TwoPrecFloat value={repoAllocation*clusterNodeCPUCount} onzero={"0"}/> per hour</td></tr>
      </tbody></Table>
    </Popover.Body>
  </Popover>}>
    <span>{children}</span>
  </OverlayTrigger>
);


const Header = ({ id, children, title }) => (
  <OverlayTrigger overlay={<Tooltip id={id}>{title}</Tooltip>}>
    <span>{children}</span>
  </OverlayTrigger>
);

class ReposTable extends Component {
  constructor(props) {
    super(props);
    this.resetState = () => { return  { repo: "", facility: "", cluster: "", allocationStartTime: "", currentAllocation: 0, clustersunallocated: [], facilityPurchased: 0, showAddModal: false, showUpdateModal: false, updateModalClusterName: "", updateModalCurrentPurchase: 0, modalError: false, modalErrorMessage: "", showToast: false, toastMsg: ""}}
    this.state = this.resetState();
    this.clusterInfo = _.keyBy(props.clusters, "name");

    this.showUpdateModal = (repoObj, compAlloc, facilityPurchased) => { 
      this.setState((prevState) => {
        let ret = this.resetState();
        ret.repo = repoObj.name;
        ret.facility = repoObj.facility;
        ret.cluster = compAlloc.clustername;
        ret.allocationStartTime = compAlloc.start;
        ret.currentAllocation = _.get(compAlloc, "percentOfFacility", 0.0);
        ret.facilityPurchased = facilityPurchased;
        ret.showUpdateModal = true;
        return ret;
      })
    }
    this.hideUpdateModal = () => { this.setState((prevState) => { return this.resetState()}) }
    this.showAddModal = (repoObj, facilityPurchased) => {
      this.setState((prevState) => {
        let ret = this.resetState();
        ret.repo = repoObj.name;
        ret.facility = repoObj.facility;
        ret.facilityPurchased = facilityPurchased;
        const purchases = _.get(_.keyBy(this.props.facilities, "name"), repoObj.facility + ".computepurchases");
        ret.clustersunallocated = _.difference(_.map(_.filter(purchases, p => p.purchased >= 0), "clustername"), _.map(_.get(repoObj, "currentComputeAllocations"), "clustername", []));
        ret.allocationStartTime = (new Date()).toISOString();
        ret.showAddModal = true;
        return ret;
      })
  }
    
    this.applyUpdateAllocation = (clustername, curalloc, currburstalloc) => { 
      if(curalloc < 0.0 || curalloc > 100.0) {
        this.setState({modalError: true, modalErrorMessage: "Please enter a number >= 0.0 and <= 100.0"});
        return;
      }
      if(currburstalloc < 0.0) {
        this.setState({modalError: true, modalErrorMessage: "Please enter a number >= 0"});
        return;
      }
      const facilityData = _.keyBy(this.props.facilities, "name")[this.state.facility]
      const facilityPurchased = _.get(_.keyBy(_.get(facilityData, "computepurchases", []), "clustername"), clustername + ".purchased", 0);
      if(facilityPurchased <= 0 && curalloc > 0.0) {
        this.setState({modalError: true, modalErrorMessage: "This facility has not purchased any compute resources in this cluster. To make this clear, please set this to 0."});
        return;
      }
      this.props.actuallyChangeAllocation(this.state.facility, this.state.repo, this.state.cluster, this.state.allocationStartTime, curalloc, currburstalloc,
        () => { 
          this.hideUpdateModal();
          this.setState({showToast: true, toastMsg: "A request to update the compute allocation has been made and approved. It will take a few seconds for this approval to be processed. Please refresh the screen after a little while to update the UI."})
        }, 
        (errormsg) => { this.setState({modalError: true, modalErrorMessage: errormsg})} );
    }

    this.applyNewAllocation = (clustername, curalloc, currburstalloc) => { 
      if(curalloc < 0.0 || curalloc > 100.0) {
        this.setState({modalError: true, modalErrorMessage: "Please enter a number >= 0.0 and <= 100.0"});
        return;
      }
      if(currburstalloc < 0.0) {
        this.setState({modalError: true, modalErrorMessage: "Please enter a number >= 0"});
        return;
      }
      const facilityData = _.keyBy(this.props.facilities, "name")[this.state.facility]
      const facilityPurchased = _.get(_.keyBy(_.get(facilityData, "computepurchases", []), "clustername"), clustername + ".purchased", 0);
      if(facilityPurchased <= 0 && curalloc > 0.0) {
        this.setState({modalError: true, modalErrorMessage: "The facility has not purchased any compute resources in this cluster. To make this clear, please set this to 0."});
        return;
      }
      this.props.actuallyChangeAllocation(this.state.facility, this.state.repo, clustername, this.state.allocationStartTime, curalloc, currburstalloc,
        () => { 
          this.hideUpdateModal();
          this.setState({showToast: true, toastMsg: "A request to update the compute allocation has been made and approved. It will take a few seconds for this approval to be processed. Please refresh the screen after a little while to update the UI."})
        }, 
        (errormsg) => { this.setState({modalError: true, modalErrorMessage: errormsg})} );
    }

    // There are only two QOSes in the system as of now - normal and preemptable
    this.includePrempt = (ev) => { 
      if(ev.target.checked) {
        this.props.setSkipQoses((current) => { return [] });
      } else {
        this.props.setSkipQoses((current) => { return [ "preemptable" ]; });
      }
    }

    this.changeHideUnused = (ev) => { 
      this.props.setHideUnused(ev.target.checked);
    }

    this.setShowAsPercentOfRepo = (ev) => { 
      this.props.setShowAsPercentOfRepo(ev.target.checked);
    }
  }

  componentDidMount() {
    this.props.setStatusbaritems([
      (<Form.Check className="sitem" inline type="switch" id="include-preemt" label="With Preempt" title="Include data from preemptable jobs" defaultChecked={!_.includes(this.props.skipQoses, "preemptable")} onChange={this.includePrempt}/>),
      (<Form.Check className="sitem" inline type="switch" id="include-unused" label="Hide unused" title="Hide usage data from repos that have not used any compute in the past month" defaultValue={this.props.hideUnused} onChange={this.changeHideUnused}/>),
      (<Form.Check className="sitem" inline type="switch" id="repo-percent" label="% of repo" title="Show as percentages of repo allocations instead of facility purchases" defaultValue={this.props.showAsPercentOfRepo} onChange={this.setShowAsPercentOfRepo}/>),
    ]);
  }

  componentWillUnmount() {
    this.props.setStatusbaritems();
  }

  render() {
    return (
      <>
      <div className="container-fluid text-center table-responsive">
        <ToastContainer className="p-3" position={"top-end"} containerPosition={"fixed"} style={{ zIndex: 1 }}>
          <Toast show={this.state.showToast} onClose={() => { this.setState({showToast: false, toastMsg: ""})}} delay={10000} autohide><Toast.Header>Info</Toast.Header><Toast.Body>{this.state.toastMsg}</Toast.Body></Toast>
        </ToastContainer>
        <table className="table table-condensed table-bordered" id="repocomputetbl">
          <thead>
            <tr>
              <th>Repo name</th>
              <th>Facility</th>
              <th>PI</th>
              <th>ClusterName</th>
              <th>Total compute allocation</th>
              <th><Header id="ph" title="Resources used in the past hour as a percentage of the facility's compute purchase in this cluster">Past hour</Header></th>
              <th><Header id="pd" title="Resources used in the past day as a percentage of the facility's compute purchase in this cluster">Past day</Header></th>
              <th><Header id="pw" title="Resources used in the past week as a percentage of the facility's compute purchase in this cluster">Past week</Header></th>
              <th><Header id="pm" title="Resources used in the past month as a percentage of the facility's compute purchase in this cluster">Past month</Header></th>
              <th><Header id="tcu" title="Resource-hours consumed for the lifetime of the repo">Total compute used</Header></th>
              <th>Start</th>
              <th>End</th>
            </tr>
          </thead>
          <tbody>
          { _.map(this.props.repos, (r) => { return (<ReposRows key={r.facility+"_"+r.name} repo={r} facilities={this.props.facilities} clusterInfo={this.clusterInfo} recentusagebycluster={this.props.recentusagebycluster} canEditAllocations={this.props.canEditAllocations} isAdmin={this.props.isAdmin} showUpdateModal={this.showUpdateModal} showAddModal={this.showAddModal} hideUnused={this.props.hideUnused} lastMonthsUsages={this.props.lastMonthsUsages} showAsPercentOfRepo={this.props.showAsPercentOfRepo}/>) }) }
          </tbody>          
          </table>
        </div>
        <UpdateComputeAllocation reponame={this.state.repo} facilityname={this.state.facility} facilities={this.props.facilities} clustername={this.state.cluster} currentAllocation={this.state.currentAllocation} facilityPurchased={this.state.facilityPurchased} showModal={this.state.showUpdateModal} showUpdateModal={this.showUpdateModal} hideModal={this.hideUpdateModal} isError={this.state.modalError} errorMessage={this.state.modalErrorMessage} applyUpdateAllocation={this.applyUpdateAllocation}/>
        <AddComputeAllocation reponame={this.state.repo} facilityname={this.state.facility} facilities={this.props.facilities} clustersunallocated={this.state.clustersunallocated} showModal={this.state.showAddModal} hideModal={this.hideUpdateModal} isError={this.state.modalError} errorMessage={this.state.modalErrorMessage} applyNewAllocation={this.applyNewAllocation}/>
      </>
     )
  }
}

class UsagesDict { 
  constructor() {
    this.usages = {};
  }

  addUsage(usg) {
    const usageindexstr = JSON.stringify({"facility": usg.facility, "repo": usg.name, "cluster": usg.clustername});
    this.usages[usageindexstr] = usg.resourceHours;
  }

  getUsage(facility, repo, cluster){ 
    return _.get(this.usages, JSON.stringify({"facility": facility, "repo": repo, "cluster": cluster}), 0);
  }
}

export default function ReposComputeListView() {
  const [ skipQoses, setSkipQoses] = useState(["preemptable"]);
  const [ hideUnused, setHideUnused] = useState(false);
  const [ showAsPercentOfRepo, setShowAsPercentOfRepo ] = useState(false);
  const { loading, error, data, refetch } = useQuery(REPOS, { variables: { skipQoses: skipQoses }});
  const [ allocreq ] = useMutation(ALLOCATION_REQUEST);
  const [ requestApproveMutation ] = useMutation(APPROVE_REQUEST_MUTATION);
  const [ toolbaritems, setToolbaritems, statusbaritems, setStatusbaritems ] = useOutletContext();


  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  let facilities = _.map(_.get(data, "facilities"), "name");
  console.log(data);
  const recentusagebycluster = {pastHour: data.pastHour, pastDay: data.pastDay, pastWeek: data.pastWeek, pastMonth: data.pastMonth};
  const lastMonthsUsages = new UsagesDict();
  _.each(recentusagebycluster.pastMonth, (usg) => lastMonthsUsages.addUsage(usg));


  const isAdmin = _.get(data, "whoami.isAdmin", false);
  let canEditAllocations = _.get(data, "whoami.isAdmin", false) ||  _.get(data, "whoami.isCzar", false);
  let approveRequest = function(reqid, callWhenDone, callOnError) {
    requestApproveMutation({ 
      variables: { Id: reqid }, 
      onCompleted: (data) => { callWhenDone(data); setTimeout(refetch, 5000) }, 
      onError: (error) => { callOnError(error.message) }, 
      refetchQueries: [ REPOS ] });
    }
  let actuallyChangeAllocation = function(facility, repo, cluster, allocationStartTime, curalloc, currburstalloc, callWhenDone, callOnError) {
    console.log("Actually change allocations to " + curalloc + " burst=" + currburstalloc + " for " + repo);
    allocreq({ variables: { request: { reqtype: "RepoComputeAllocation", facilityname: facility, reponame: repo, clustername: cluster, start: allocationStartTime, percentOfFacility: _.toNumber(curalloc), burstPercentOfFacility: _.toNumber(currburstalloc) } }, 
      onCompleted: (data) => { console.log(data); approveRequest(data["requestRepoComputeAllocation"]["Id"], callWhenDone, callOnError)},
      onError: (error) => { console.log(error); callOnError(error.message)}});
  }
  return (
    <>
    <ReposTable repos={data.myRepos} facilities={data.facilities} clusters={data.clusters} recentusagebycluster={recentusagebycluster}
      isAdmin={isAdmin} canEditAllocations={canEditAllocations} actuallyChangeAllocation={actuallyChangeAllocation}
      statusbaritems={statusbaritems} setStatusbaritems={setStatusbaritems}
      skipQoses={skipQoses} setSkipQoses={setSkipQoses}
      showAsPercentOfRepo={showAsPercentOfRepo} setShowAsPercentOfRepo={setShowAsPercentOfRepo}
      lastMonthsUsages={lastMonthsUsages} hideUnused={hideUnused} setHideUnused={setHideUnused}
      />
    </>
  );
}
