import _ from "lodash";
import { NavLink } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Modal from 'react-bootstrap/Modal';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import ListGroup from 'react-bootstrap/ListGroup';

const REPOS = gql`
query{
  myRepos {
    Id
    name
    facility
    principal
    currentStorageAllocations {
      Id
      storagename
      purpose
      start
      end
      gigabytes
      usage {
        gigabytes
      }
    }
  }
  whoami {
    username
  }
  facilities {
    name
  }
}`;

class ReposRows extends Component {
  constructor(props) {
    super(props);
    this.reponame = props.repo.name;
    this.facilityname = props.repo.facility;
  }
  render() {
    var first = true;
    let cas = _.get(this.props.repo, "currentStorageAllocations", [{}]), rows = cas.length;
    let trs = _.map(cas, (a) => {
      if(first) {
        first = false;
        return (
          <tr key={this.facilityname+this.reponame+a.storagename+a.purpose} data-name={this.reponame}>
            <td rowSpan={rows} className="vmid">{this.reponame}</td>
            <td rowSpan={rows} className="vmid">{this.props.repo.facility}</td>
            <td rowSpan={rows} className="vmid">{this.props.repo.principal}</td>
            <td><NavLink to={"/repos/storage/"+this.props.repo.facility+"/"+this.reponame+"/allocation/"+a.Id} key={this.reponame}>{a.purpose}</NavLink></td>
            <td>{a.gigabytes}</td>
            <td>{a.usage.gigabytes}</td>
          </tr>)
        } else {
          return (
            <tr key={this.facilityname+this.reponame+a.storagename+a.purpose} data-name={this.reponame}>
              <td><NavLink to={"/repos/storage/"+this.props.repo.facility+"/"+this.reponame+"/allocation/"+a.Id} key={this.reponame}>{a.purpose}</NavLink></td>
              <td>{a.gigabytes}</td>
              <td>{a.usage.gigabytes}</td>
            </tr>)
        }
    });
    return ( <tbody>{trs}</tbody> )
  }
}


class ReposTable extends Component {
  constructor(props) {
    super(props);
  }
  render() {
    return (
      <>
      <div className="container-fluid text-center table-responsive">
        <table className="table table-condensed table-striped table-bordered">
          <thead>
            <tr><th>Repo name</th><th>Facility</th><th>PI</th><th>Purpose</th><th>Total storage allocation (GB)</th><th>Total storage used (GB)</th></tr>
          </thead>
          { _.map(this.props.repos, (r) => { return (<ReposRows key={r.facility+"_"+r.name} repo={r}/>) }) }
          </table>
        </div>
      </>
     )
  }
}

export default function ReposStorageListView() {
  const { loading, error, data } = useQuery(REPOS);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  let facilities = _.map(_.get(data, "facilities"), "name");
  console.log(data);

  return (
    <>
    <ReposTable repos={data.myRepos} />
    </>
  );
}
