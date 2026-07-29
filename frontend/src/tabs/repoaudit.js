import _ from "lodash";
import { NavLink, useParams } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import { TwoPrecFloat, DateTimeDisp } from "./widgets";
import { req2audit } from "../bpl/requests";


const REPOAUDIT = gql`
query repoAuditTrails($repo: String!, $facility: String!){
  repoAuditTrails(repo: { name: $repo, facility: $facility } ) {
    Id
    type
    action
    actedby
    actedat
    details
  }
  requests(fetchprocessed: true, showmine: false, filter: { reponame: $repo }) {
    Id
    reqtype
    requestedby
    timeofrequest
    approvalstatus
    username
    notes
    audit {
      actedby
      actedat
      notes
      previous
    }
}
  whoami {
    username
  }
}`;

class AuditTable extends Component {
  constructor(props) {
    super(props);

    let reqs = _.flatten(_.map(this.props.requests, (req) => { return req2audit(req) }));
    _.each(reqs, (r) => { r["isRequest"] = true} )
    let combined = _.reverse(_.sortBy(_.concat(reqs, _.map(this.props.audittrail, (a) => { let ac = _.clone(a); ac["isRequest"] = false; return ac })), (c) => { return new Date(c["actedat"]) }))
    this.state = { combined: combined }
  }

  render() {
    return (
      <>
      <div className="container-fluid text-center table-responsive">
        <table className="table table-condensed table-striped table-bordered">
          <thead>
            <tr className="d-flex"><th className="col-2">At</th><th className="col-2">By</th><th className="col-3">Action</th><th className="col-2">Status</th><th className="col-3">Details</th></tr>
          </thead>
          <tbody>
          { _.map(this.state.combined, (a, i) => { return (
            <tr key={i} className="d-flex">
              <td className="col-2"><DateTimeDisp value={a.actedat}/>{ a.isRequest ? <span className="float-end text-warning"><>&larr;</></span> : ""}</td>
              <td className="col-2">{a.actedby}</td>
              <td className="col-3">{a.action}</td>
              <td className="col-2">{a.status}</td>
              <td className="col-3 text-truncate">{a.details}</td>
            </tr>) }) }
          </tbody>
          </table>
        </div>
      </>
     )
  }
}

export default function RepoAuditTrail() {
  let params = useParams(), reponame = params.name, facilityname = params.facility;
  const { loading, error, data } = useQuery(REPOAUDIT, { variables: { repo: reponame, facility: facilityname } }, { fetchPolicy: 'no-cache', nextFetchPolicy: 'no-cache'});

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  console.log(data);

  return (
    <>
    <AuditTable audittrail={data.repoAuditTrails} requests={data.requests}/>
    </>
  );
}
