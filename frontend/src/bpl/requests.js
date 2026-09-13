import _ from "lodash";

export function req2audit(req) {
    let details = "";
    switch(req.reqtype) {
        case "RepoMembership":
        case "RepoRemoveUser":
            details = req.username + " ";
            break;
        case "RepoComputeAllocation":
            details = req.clustername + " ";
            break;
        case "RepoStorageAllocation":
            details = req.purpose + " ";
            break;
        case "RepoChangeComputeRequirement":
            details = _.get(req, "computerequirement", "") + " ";
            break;
    }
    let allads = _.concat([{actedby: req.requestedby, actedat: req.timeofrequest, action: req.reqtype, details: details + _.get(req, "notes", "")}], _.map(_.get(req, "audit", []), (a) => { return { actedby: a.actedby, action: req.reqtype, actedat: a.actedat, details: details + _.get(a, "notes", "") } }));
    let allsts = _.concat(_.map(_.get(req, "audit", []), (a) => { return { status: _.get(a, "previous", "Incomplete") } }), [{status: req.approvalstatus}]);
    let cmbads = _.zipWith(allads, allsts, (a, s) => { a["status"] = s["status"]; return a})
    console.log(cmbads);
    return cmbads;
}
