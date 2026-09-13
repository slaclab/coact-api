import _ from "lodash";
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate
} from "react-router-dom";
import {
  ApolloClient,
  InMemoryCache,
  ApolloProvider,
  useQuery,
  gql
} from "@apollo/client";
import LandingPage from "./landingpage";
import FakeLogin from "./fakelogin";
import TopNavBar from "./nav";
import Facilities from "./tabs/facilities";
import Facility from "./tabs/facility";
import RepoTabs from "./tabs/repostabs";
import RequestTypes from "./tabs/requesttypes";
import MyProfile from "./myprofile";
import RegisterUser from "./register";
import Compute from "./tabs/compute";
import Storage from "./tabs/storage";
import Users from "./tabs/users";
import Groups from "./tabs/groups";
import ClustersTabs from "./tabs/clusterstabs";
import StorageTabs from "./tabs/storagetabs";
import ReposComputeListView from "./tabs/reposcompute";
import ReposStorageListView from "./tabs/reposstorage";
import ReposUsersListView from "./tabs/reposusers";
import ReposGroupsListView from "./tabs/reposgroups";
import UserAuditTrail from "./tabs/useraudit";
import ReposAuditListView from "./tabs/reposaudit";
import RepoAuditTrail from "./tabs/repoaudit";
import RepoFeatures from "./tabs/repofeatures";
import ReposInfoListView from "./tabs/reposinfo";
import Requests from "./tabs/requests";
import './index.css';
import { Footer } from "./tabs/widgets";
import { Nav } from 'react-bootstrap';
import Tab from 'react-bootstrap/Tab';
import { Link, Outlet, useParams } from "react-router-dom";

const client = new ApolloClient({
  uri: process.env.REACT_APP_COACT_GRAPHQL_URI,
  cache: new InMemoryCache(),
  headers: { coactimp: localStorage.getItem('imptk'), coactshowall: localStorage.getItem("showallrepos") == null || "true"==localStorage.getItem("showallrepos") }
});

const container = document.getElementById('root');
const root = createRoot(container);

const HOMEDETAILS = gql`
query {
  amIRegistered {
    isRegistered
    isRegistrationPending
    eppn
    fullname
  }
}
`;

function App() {
  console.log("starting app....");
  const [reposActiveTab, setReposActiveTab] = useState("info");
  const [requestsActiveTab, setRequestsActiveTab] = useState("");
  const { loading, error, data } = useQuery(HOMEDETAILS, { errorPolicy: 'all'} );
  if (loading) return <p>Loading...</p>;
  // if (error) return <p>Error!</p>;
  console.log(data);
  let hasUserAcc = _.get(data, "amIRegistered.isRegistered", false);
  let eppn = _.get(data, "amIRegistered.eppn", null);
  let registrationPending = _.get(data, "amIRegistered.isRegistrationPending", false);
  let isRegistered = _.get(data, "amIRegistered.isRegistered", false);
  let fullname = _.get(data, "amIRegistered.fullname", "");

  const RedirectUrl = ({ url }) => {
    window.location.href = url;
    return <h5>Redirecting...</h5>;
  };

  if(_.isEmpty(requestsActiveTab) && /requests\/(\w+)/.test(window.location.pathname)) {
    const tabFromUrl = window.location.pathname.match(/requests\/(\w+)/)[1];
    console.log("Setting active requests tab to " + tabFromUrl);
    setRequestsActiveTab(tabFromUrl);
  }

  return (
    <div id="mainContainer">
      <div className="header">
        <BrowserRouter>
        { hasUserAcc ? <TopNavBar setReposActiveTab={setReposActiveTab} /> : <div/> }
        <Routes>
          <Route exact path="/" element={ hasUserAcc ? <Navigate to="myprofile" /> : <LandingPage/> } />
          <Route exact path="/login" element={ hasUserAcc ? <Navigate to="../myprofile" /> : <Navigate to="../register" /> } />
          <Route exact path="/logout" element={<RedirectUrl url="https://vouch.slac.stanford.edu/logout" />} />
          <Route exact path="register" element={<RegisterUser eppn={eppn} isRegistered={isRegistered} registrationPending={registrationPending} fullname={fullname}/>}/>
          <Route exact path="facilities" element={<Facilities />}/>
          <Route exact path="facilities/:facilityname" element={<Facility />}/>
          <Route exact path="myprofile" element={<MyProfile />}/>
          <Route exact path="myaudittrail" element={<UserAuditTrail type={"User"} />}/>
          <Route exact path="clusterusage/:clustername" element={<ClustersTabs />} />
          <Route exact path="storageusage/:storagename" element={<StorageTabs />} />
          <Route exact path="storageusage/:storagename/purpose/:purpose" element={<StorageTabs />} />
          <Route exact path="repos" element={<RepoTabs reposActiveTab={reposActiveTab} setReposActiveTab={setReposActiveTab} />}>
            <Route exact path={`compute`} element={ <ReposComputeListView/> }/>
            <Route exact path={`compute/:facility/:name/allocation/:allocationid`} element={ <Compute/> }/>
            <Route exact path={`storage`} element={ <ReposStorageListView/> } />
            <Route exact path={`storage/:facility/:name/allocation/:allocationid`} element={ <Storage/> }/>
            <Route exact path={`users`} element = { <ReposUsersListView/>} />
            <Route exact path={`users/:facility/:name`} element = { <Users />} />
            <Route exact path={`groups`} element = { <ReposGroupsListView/> } />
            <Route exact path={`groups/:facility/:name`} element = { <Groups /> } />
            <Route exact path={`audit`} element = { <ReposAuditListView/>} />
            <Route exact path={`audit/:facility/:name`} element = { <RepoAuditTrail />} />
            <Route exact path={`info`} element = { <ReposInfoListView />} />
            <Route exact path={`features/:facility/:name`} element = { <RepoFeatures />} />
          </Route>
          <Route exact path={`requests`} element={<Requests showall={true} showmine={false} setRequestsActiveTab={setRequestsActiveTab} />} />
        </Routes>
        </BrowserRouter>
      </div>
      <Footer/>
    </div>
  );
}


root.render(
  <ApolloProvider client={client}>
    <App/>
  </ApolloProvider>
);
