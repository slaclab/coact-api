import { useQuery, useMutation, gql } from "@apollo/client";
import _ from "lodash";
import React, { Component, useState } from 'react';
import { Link, Outlet } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Facility from "../tabs/facility";


const FACILITYDETAILS = gql`
query {
  facilitiesIManage {
    name
  }
}
`;

class RequestNewFacility extends Component {
  render() {
    return <Button variant="secondary">Request New Facility</Button>
  }
}

export default function Facilities() {
  const { loading, error, data } = useQuery(FACILITYDETAILS, { errorPolicy: 'all'} );
  const [selectedFacility, setSelectedFacility] = useState("");

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  const triggerDetails = function(facilityname) {
    console.log("Selected " + facilityname);
    setSelectedFacility(facilityname)
  }

  console.log(data);
  let facilities = _.sortBy(data.facilitiesIManage, "name");
  let firstFacility = _.get(facilities, "[0].name", "");

  return (<div id="facilities">
    <Tabs
      defaultActiveKey={firstFacility}
      id="facilities-tab"
      className="mb-3"
    >
    { facilities.map((facility) => (
      <Tab key={facility.name} eventKey={facility.name} title={facility.name} mountOnEnter={true} unmountOnExit={true}>
        <Facility facilityname={facility.name}/>
      </Tab>
    ))}
    </Tabs>
  </div>);
}
