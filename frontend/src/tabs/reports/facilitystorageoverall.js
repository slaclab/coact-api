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
import { TeraBytes, InMillions } from "../widgets";


const BYDAYREPORT = gql`
query report($storagename: String!, $purpose: String){
  reportFacilityStorage(storagename: $storagename, purpose: $purpose) {
    repo
    gigabytes
    purpose
  }
}
`;


export default function FacilityStorageOverall(props) {
  const { loading, error, data } = useQuery(BYDAYREPORT, { variables: { storagename: props.storagename, purpose: props.purpose } }, { errorPolicy: 'all'} );

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  console.log(data);
  let usage = data.reportFacilityStorage;

  return (
    <Table bordered>
      <thead><tr><th>Repo</th>{_.isNil(props.purpose) ? "" : <th>Purpose</th>}<th>Storage used (in TB)</th></tr></thead>
      <tbody>
        { _.map(usage, (u) => { return (<tr key={u.repo}><td>{u.repo}</td>{_.isNil(props.purpose) ? "" : <td>{u.purpose}</td>}<td><TeraBytes value={u.gigabytes}/></td></tr>) }) }
      </tbody>
    </Table>
  );
}
