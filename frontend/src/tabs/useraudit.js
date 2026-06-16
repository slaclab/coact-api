import _ from "lodash";
import { NavLink } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import { TwoPrecFloat, DateTimeDisp } from "./widgets";

const REPOS = gql`
query{
  userAuditTrails {
    type
    action
    actedby
    actedat
    details
  }
  whoami {
    username
  }
}`;


class AuditTable extends Component {
  constructor(props) {
    super(props);
  }
  render() {
    return (
      <>
      <div className="container-fluid text-center table-responsive">
        <table className="table table-condensed table-striped table-bordered">
          <thead>
            <tr><th>Action</th><th>By</th><th>At</th><th>Details</th></tr>
          </thead>
          <tbody>
          { _.map(this.props.audittrail, (a) => { return (<tr><td>{a.action}</td><td>{a.actedby}</td><td><DateTimeDisp value={a.actedat}/></td><td>{a.details}</td></tr>) }) }
          </tbody>
          </table>
        </div>
      </>
     )
  }
}

export default function UserAuditTrail() {
  const { loading, error, data } = useQuery(REPOS);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  console.log(data);

  return (
    <>
    <AuditTable audittrail={data.userAuditTrails} />
    </>
  );
}
