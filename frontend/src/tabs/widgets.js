import _ from "lodash";
import dayjs from "dayjs";
import React from "react";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Image from 'react-bootstrap/Image'
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import { ButtonGroup, Nav, Navbar } from 'react-bootstrap';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import SLACLogo from '../images/SLAC_primary_red_small.png';
import StanfordDOELogo from '../images/Stanford_DOE_black.png';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCheck, faMehBlank, faRocket, faTrash, faXmark } from '@fortawesome/free-solid-svg-icons'

export function TwoPrecFloat(props) {
  if(_.isNil(props.value)) return "N/A";
  if(props.value > 99999998) return "Inf";
  if(props.value == 0) return props.onzero ?? "";
  return (props.value).toFixed(2);
}

export function TwoPrecPercent(props) {
  if(_.isNil(props.value)) return "(N/A)";
  if(props.value > 99999998) return "(Inf)";
  if(props.value == 0) return "";
  return "(" + (props.value).toFixed(2) + "%)";
}

export function ChargeFactor(props) {
  if(_.isNil(props.value)) return "N/A";
  return props.value.toFixed(2);
}

export function TeraBytes(props) {
  if(_.isNil(props.value)) return "N/A";
  return (props.value/1000.0).toFixed(2);
}

export function InMillions(props) {
  if(_.isNil(props.value)) return "N/A";
  return (props.value/1000000.0).toFixed(2);
}

export function DateDisp(props) {
  if(_.isNil(props.value)) return "N/A";
  return dayjs(props.value).format('MMM D YYYY');
}

export function DateTimeDisp(props) {
  if(_.isNil(props.value)) return "N/A";
  return dayjs(props.value).format('MMM D YYYY HH:mm:ss');
}

export function YesNo(props) {
  if(_.isNil(props.value)) return (<span><FontAwesomeIcon icon={faMehBlank}/></span>);
  return props.value ?  (<span className="text-info"><FontAwesomeIcon icon={faCheck} size="lg"/></span>) : (<span className="text-danger"><FontAwesomeIcon icon={faXmark} size="lg"/></span>);
}


// props 1) getmatches Function with callback with a list of matches for passed in srchtext - ideal for useLazyQuery. 2) selected - those that are currently selected. 3) onSelDesel - function to process selection/deselection.
export class SearchAndAdd extends React.Component {
  constructor(props) {
    super(props);
    this.state = { selected: this.props.selected, matches: [  ] }

    this.handleTyping = (event) => {
      let srchtxt = event.target.value;
      if(srchtxt.length > 2) {
        this.props.getmatches(srchtxt, (matches) => { this.setState({ matches: _.map(matches, (x) => { return {"label": x, "selected": _.includes(this.state.selected, x)}  }) }); });
      }
    }

    this.checkUncheck = (event) => {
      let selkey = event.target.dataset.selkey;
      console.log(selkey + " has value " + event.target.checked);
      this.props.onSelDesel(selkey, event.target.checked);
      let newselected = event.target.checked ? _.union(this.state.selected, [selkey]) : _.without(this.state.selected, selkey);
      let newmatches = _.map(this.state.matches, (x) => { return {"label": x["label"], "selected": _.includes(newselected, x["label"])}  });
      this.setState({ selected: newselected, matches: newmatches});
    }
  }

  render() {
    return(
      <div className="table-responsive">
        <Form.Group className="mb-3">
          <Form.Label className="pe-2">{this.props.label}</Form.Label>
          <Form.Control type="text" placeholder={"Please type in a " + _.toLower(this.props.label)} onChange={this.handleTyping}/>
        </Form.Group>
        <table className="table table-condensed table-striped table-bordered">
          <thead><tr><th>{this.props.label}</th><th>Select</th></tr></thead>
          <tbody>{ _.map(this.state.matches, (u) => { return (<tr key={u.label}><td>{u.label}</td><td><input type="checkbox" data-selkey={u.label} checked={!!u.selected} onChange={this.checkUncheck}/></td></tr>) }) }</tbody>
        </table>
      </div>
    );
  }
}

export class BulkSearchAndAdd extends React.Component {
  constructor(props) {
    super(props);
    this.state = { usertxt: "", selected: this.props.selected, matches: [  ] }

    this.handleTyping = (event) => {
      this.setState({usertxt: event.target.value});
    }
    this.lookup = () => { 
      let lines = _.reject(_.split(this.state.usertxt, "\n"), (x) => { return x.length < 3});
      console.log(lines);
      this.props.getmatches(lines, (matches) => {
        console.log(matches);
        this.setState({ matches: _.map(matches, (x) => { return {"label": x, "selected": _.includes(this.state.selected, x)}  }) })
      })
    }

    this.checkUncheckAll = (event) => {
      let checkedstatus = event.target.checked;
      this.setState((prevstate) => {         
        return {
          usertxt: "", 
          selected: checkedstatus ? _.map(prevstate.matches, "label") : [], 
          matches: _.map(prevstate.matches, (x) => { return {"label": x["label"], "selected": checkedstatus }})
        };
      })
    } 

    this.checkUncheck = (event) => {
      let selkey = event.target.dataset.selkey;
      this.setState((prevstate) => { 
        return {
          usertxt: "", 
          selected: event.target.checked ? _.union(this.state.selected, [selkey]) : _.without(this.state.selected, selkey), 
          matches: _.map(prevstate.matches, (x) => { if(x["label"] == selkey ) { x["selected"] = event.target.checked; return x } else { return x} })
        }
      })      
    }

    this.apply = (event) => {
      _.each(this.state.matches, function(x){
        if(x["selected"] && !_.includes(props.selected, x["label"])) {
          console.log("Need to add " + x["label"] + " to repo");
          props.onSelDesel(x["label"], true);
        } else if(!x["selected"] && _.includes(props.selected, x["label"])) {
          console.log("Need to remove " + x["label"] + " from repo");
          props.onSelDesel(x["label"], false);
        }
      })
    }
  }

  render() {
    return(
      <div className="table-responsive srchadd">
        <Form.Group className="mb-3">
          <Form.Label className="pe-2">{this.props.label}</Form.Label>
          <Form.Control type="textarea" as="textarea" rows={3} placeholder={"Please type in a " + _.toLower(this.props.label)} onChange={this.handleTyping}/>
          <div className="btns">
            <Button variant="light" onClick={this.props.hideModal}>Close</Button>
            <Button variant="secondary" onClick={this.lookup}>Lookup</Button>
            <Button onClick={this.apply}>Apply</Button>
          </div>
        </Form.Group>
        <table className="table table-condensed table-striped table-bordered">
          <thead><tr><th>{this.props.label}</th><th>Select <span className="px-2"><input type="checkbox" onChange={this.checkUncheckAll}/></span></th></tr></thead>
          <tbody>{ _.map(this.state.matches, (u) => { return (<tr key={u.label}><td>{u.label}</td><td><input type="checkbox" data-selkey={u.label} checked={!!u.selected} onChange={this.checkUncheck}/></td></tr>) }) }</tbody>
        </table>
      </div>
    );
  }
}


export function NoNavHeader() { // Use for pages that do have a navbar on top.
  return (
    <Navbar bg="primary" variant="dark" expand="lg">
      <Navbar.Brand className="px-2"><FontAwesomeIcon icon={faRocket} size="lg"/> Coact</Navbar.Brand>
      <Navbar.Toggle onClick={function noRefCheck(){}} />
      <Navbar.Toggle aria-controls="basic-navbar-nav" />
      <Navbar.Collapse id="basic-navbar-nav">
      </Navbar.Collapse>
      <Nav>
      </Nav>
    </Navbar>
  )
}

export function Footer() {
  return (
     <div className="footer">
      <Row>
        <Col><a href="https://www.slac.stanford.edu"><Image id="slac_logo" height={"30vh"} src={SLACLogo} style={({marginTop: '11px'})}/></a></Col>
        <Col><Image height={"50vh"} src={StanfordDOELogo} className="partner float-end"/></Col>
      </Row>
     </div>
  )
}

export function ErrorMsgModal(props) { // Sometimes, it's easier to show error messages in a modal
  return (
    <Modal show={props.show} onHide={() => {props.setShow(false)}}>
      <Modal.Header closeButton>
        <Modal.Title>{props.title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Alert>{props.message}</Alert>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="light" onClick={() => {props.setShow(false)}}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  )
}

export function ToolbarButton(props) {
  const showMdl = () => { props.setShow(true); }
  return (
    <Button variant="secondary" className="tlbrbtn" onClick={showMdl}>{props.label}</Button>
  );
}

export function submitOnEnter(submitfn) {
  return (event) => {
    if(event.key === "Enter") {
      submitfn();
    }
  }
}


export class StringListManager extends React.Component {
  constructor(props) {
    super(props);
    this.state = { newItem: "", validationError: false, validationErrorMsg: "" }
    this.setNewItem = (ev) => { this.setState({newItem: ev.target.value})}
    this.addItem = (ev) => { 
      if(_.isEmpty(this.state.newItem)) {
        this.setState({validationError: true, validationErrorMsg: "Please enter a valid string value"});
        return;
      }
      props.addItem(this.state.newItem);
      this.setState({ newItem: "", validationError: false, validationErrorMsg: ""})
    }
    this.removeItem = (item) => { 
      props.removeItem(item);
    }
  }

  render() {
    return(
      <div className="table-responsive">
        <div className="stringlistmgr">
          { _.map(this.props.items, (u) => { return (<Row className="item" key={u}><Col>{u}</Col><Col md={1} className="text-primary"><span onClick={() => this.removeItem(u)}><FontAwesomeIcon icon={faTrash}/></span></Col></Row>) })}
        </div>
        <Form.Group className="my-3">
          <InputGroup hasValidation>
            <Form.Control type="text" isInvalid={this.state.validationError} onChange={this.setNewItem} onBlur={this.addItem} value={this.state.newItem}/>
            <Form.Control.Feedback type="invalid">{this.state.validationErrorMsg}</Form.Control.Feedback>
          </InputGroup>
          <Button className="my-2" variant="secondary" onClick={this.addItem}>{this.props.addLabel}</Button>
          </Form.Group>
        </div>
    );
  }
}