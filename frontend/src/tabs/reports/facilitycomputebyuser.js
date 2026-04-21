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
query report($clustername: String!, $range: ReportRangeInput!){
  reportFacilityComputeByUser(clustername: $clustername, range: $range) {
    repo
    facility
    username
    resourceHours
  }
}
`;


export default function FacilityComputeByUser(props) {
  const { loading, error, data } = useQuery(BYDAYREPORT, { variables: { clustername: props.clustername, range: { start: props.startDate, end: props.endDate } } }, { errorPolicy: 'all'} );

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  console.log(data);
  let usage = data.reportFacilityComputeByUser;

  return (
    <div className="text-center">
      <h5>Compute usage for cluster <span className="text-primary">{props.clustername}</span></h5>
      <Table bordered>
        <thead><tr><th>Facility</th><th>Repo</th><th>User</th><th>Compute hours used</th></tr></thead>
        <tbody>
          { _.map(usage, (u) => { return (<tr key={u.facility+u.repo+u.username}><td>{u.facility}</td><td>{u.repo}</td><td>{u.username}</td><td><TwoPrecFloat value={u.resourceHours}/></td></tr>) }) }
        </tbody>
      </Table>
    </div>
  );
}
