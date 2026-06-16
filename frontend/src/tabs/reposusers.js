import _ from "lodash";
import { NavLink } from "react-router-dom";
import { useQuery, useMutation, gql } from "@apollo/client";
import React, { Component, useState } from 'react';

const REPOS = gql`
query{
  myRepos {
    name
    principal
    facility
  }
  whoami {
    username
  }
}`;

class ReposRows extends Component {
  constructor(props) {
    super(props);
  }
  render() {
      return (
        <tr key={this.props.repo.facility+"_"+this.props.repo.name}>
          <td className="vmid"><NavLink to={"/repos/users/"+this.props.repo.facility+"/"+this.props.repo.name}>{this.props.repo.name}</NavLink></td>
          <td className="vmid">{this.props.repo.facility}</td>
          <td className="vmid">{this.props.repo.principal}</td>
        </tr>
      );
  }
}


class ReposTable extends Component {
  constructor(props) {
    super(props);
  }
  render() {
    return (
      <>
      <div className="container-fluid text-center">
        <table className="table table-condensed table-striped table-bordered table-responsive">
          <thead>
            <tr><th>Repo name</th><th>Facility</th><th>PI</th></tr>
          </thead>
          <tbody>
            { _.map(this.props.repos, (r) => { return (<ReposRows key={r.facility+"_"+r.name} repo={r}/>) }) }
          </tbody>
        </table>
      </div>
      </>
     )
  }
}

export default function ReposUsersListView() {
  const { loading, error, data } = useQuery(REPOS);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error :</p>;

  let username = _.get(data, "whoami.username");
  console.log(data);

  return (
    <>
    <ReposTable repos={data.myRepos} />
    </>
  );
}
