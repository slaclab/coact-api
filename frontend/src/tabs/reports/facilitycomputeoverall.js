import { useQuery, gql } from "@apollo/client";
import _ from "lodash";
import React, { Component, useState } from 'react';
import Plot from "react-plotly.js";

const BYDAYREPORT = gql`
query report($clustername: String!, $group: String!){
  reportFacilityComputeOverall(clustername: $clustername, group: $group) {
    facility
    date
    resourceHours
  }
}
`;

export default function FacilityComputeOverall(props) {
  const { loading, error, data } = useQuery(BYDAYREPORT, { variables: { clustername: props.clustername, group: props.group } }, { errorPolicy: 'all'} );

  if (loading) return <p>Loading...</p>;
//  if (error) return <p>Error :</p>;

  console.log(data);
  let usage = data.reportFacilityComputeOverall;

  // We create a stacked area chart.
  let byfac = _.groupBy(usage, "facility");
  let traces = _.map(byfac, (v,k) => { return { name: k, stackgroup: "one", x: _.map(v, "date"), y: _.map(v, "resourceHours") }})
  let layout = { showlegend: true, legend: { x: 0.075, xanchor: 'center', y: 0.98, font: { family: 'Optima, Helevetica, Lucida Grande, Lucida Sans, sans-serif', size: 14, color: '#000' } }, autosize: false, width: window.innerWidth, height: 0.9*window.innerHeight, margin: { t: 0, b: -0.1 } };


  return (
    <div className="text-center">
      <h5>Overall compute usage for cluster <span className="text-primary">{props.clustername}</span></h5>
      <div className="facoverall">
        <Plot data={traces} layout={layout} style={{width: "100%", height: "100%"}} />
      </div>
    </div>
);
}
