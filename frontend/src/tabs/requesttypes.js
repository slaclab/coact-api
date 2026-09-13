import _ from "lodash";
import { Link, Outlet } from "react-router-dom";
import Tab from 'react-bootstrap/Tab';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';

export default function RequestTypesTab(props) {  
  return (<div id="requesttypes">
    <Tab.Container activeKey={props.requestsActiveTab} onSelect={(selKey) => { props.setRequestsActiveTab(selKey); }} >
        <Row id="requeststabs">
          <Col>
            <Nav variant="tabs">
              <Nav.Item>
                <Nav.Link eventKey="myrequests" as={Link} to={`myrequests`}>My Requests</Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="pending" as={Link} to={`pending`}>Pending Requests</Nav.Link>
              </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="all" as={Link} to={`all`}>All Requests</Nav.Link>
                </Nav.Item>
              </Nav>
            </Col>
        </Row>
        <Tab.Content>
          <Outlet/>
        </Tab.Content>
    </Tab.Container>
  </div>);
}
