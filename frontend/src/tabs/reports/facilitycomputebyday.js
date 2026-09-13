import { useQuery, gql } from "@apollo/client";
import _ from "lodash";
import dayjs from "dayjs";
import React, { Component, useState } from 'react';
import { Link, Outlet } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import { DateDisp, TwoPrecFloat } from "../widgets";


const BYDAYREPORT = gql`
query report($clustername: String!, $range: ReportRangeInput!, $group: String!){
  reportFacilityComputeByDay(clustername: $clustername, range: $range, group: $group) {
    repo
    facility
    date
    resourceHours
  }
}
`;


export default function FacilityComputeByDay(props) {
  const { loading, error, data } = useQuery(BYDAYREPORT, { variables: { clustername: props.clustername, range: { start: props.startDate, end: props.endDate }, group: props.group } }, { errorPolicy: 'all'} );

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  console.log(data);
  let usage = data.reportFacilityComputeByDay;

  return (
    <div className="text-center">
      <h5>Compute usage for cluster <span className="text-primary">{props.clustername}</span></h5>
      <Table bordered>
        <thead><tr><th>Repo</th><th>Facility</th><th>Date</th><th>Compute hours used</th></tr></thead>
        <tbody>
          { _.map(usage, (u) => { return (<tr key={u.facility+u.repo+u.date}><td>{u.repo}</td><td>{u.facility}</td><td><DateDisp value={u.date}/></td><td><TwoPrecFloat value={u.resourceHours}/></td></tr>) }) }
        </tbody>
      </Table>
    </div>
  );
}
