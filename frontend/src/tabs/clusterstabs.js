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

import FacilityComputeByDay from "./reports/facilitycomputebyday";
import FacilityComputeByUser from "./reports/facilitycomputebyuser";
import FacilityComputeOverall from "./reports/facilitycomputeoverall";

const WHOAMI = gql`
query{
  whoami {
    username
  }
  facilities {
    name
  }
}`;


export default function ClusterTabs() {
  let params = useParams(), clustername = params.clustername;
  const { loading, error, data } = useQuery(WHOAMI);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  let facilities = _.map(_.get(data, "facilities"), "name");

  return (<Tab.Container id="clusterreports" defaultActiveKey="cluster">
    <Tabs defaultActiveKey="by_day_week" className="mb-3" mountOnEnter={true} unmountOnExit={true}>
      <Tab eventKey="by_day_week" title="By day - week">
        <FacilityComputeByDay clustername={clustername} startDate={dayjs().subtract(7, 'day').toDate()} endDate={dayjs().toDate()} group="Day" />
      </Tab>
      <Tab eventKey="by_day_month" title="By day - month">
        <FacilityComputeByDay clustername={clustername} startDate={dayjs().subtract(1, 'month').toDate()} endDate={dayjs().toDate()} group="Day" />
      </Tab>
      <Tab eventKey="by_month_year" title="By month - year">
        <FacilityComputeByDay clustername={clustername} startDate={dayjs().subtract(1, 'year').toDate()} endDate={dayjs().toDate()} group="Month" />
      </Tab>
      <Tab eventKey="by_user_day" title="By user - day">
        <FacilityComputeByUser clustername={clustername} startDate={dayjs().subtract(1, 'days').toDate()} endDate={dayjs().toDate()} />
      </Tab>
      <Tab eventKey="by_user_past2" title="By user - past 2 days">
        <FacilityComputeByUser clustername={clustername} startDate={dayjs().subtract(2, 'days').toDate()} endDate={dayjs().toDate()} />
      </Tab>
      <Tab eventKey="by_user_weel" title="By user - week">
       <FacilityComputeByUser clustername={clustername} startDate={dayjs().subtract(7, 'day').toDate()} endDate={dayjs().toDate()} />
      </Tab>
      <Tab eventKey="by_user_month" title="By user - month">
        <FacilityComputeByUser clustername={clustername} startDate={dayjs().subtract(1, 'month').toDate()} endDate={dayjs().toDate()} />
      </Tab>
      <Tab eventKey="by_facility_daily" title="By facility, daily">
        <FacilityComputeOverall clustername={clustername}  group="Day" />
      </Tab>
      <Tab eventKey="by_facility_weekly" title="By facility, weekly">
        <FacilityComputeOverall clustername={clustername}  group="Week" />
      </Tab>
      <Tab eventKey="by_facility_monthly" title="By facility, monthly">
        <FacilityComputeOverall clustername={clustername}  group="Month" />
      </Tab>
      </Tabs>
    </Tab.Container>
  );
}
