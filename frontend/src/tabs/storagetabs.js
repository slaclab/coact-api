import _ from "lodash";
import React, { Component, useState } from 'react';
import { useQuery, useMutation, gql } from "@apollo/client";
import { useParams } from "react-router-dom";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';
import dayjs from "dayjs";

import FacilityStorageOverall from "./reports/facilitystorageoverall";


const WHOAMI = gql`
query{
  whoami {
    username
  }
  facilities {
    name
  }
}`;


export default function StorageTabs() {
  let params = useParams(), storagename = params.storagename, purpose = params.purpose;
  const { loading, error, data } = useQuery(WHOAMI);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  let facilities = _.map(_.get(data, "facilities"), "name");

  return (
    <FacilityStorageOverall storagename={storagename} purpose={purpose} />
  );
}
