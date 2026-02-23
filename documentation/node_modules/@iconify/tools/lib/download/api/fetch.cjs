'use strict';

let customFetch = fetch;
function setFetch(fetchFunction) {
  customFetch = fetchFunction;
}
function getFetch() {
  return customFetch;
}

exports.getFetch = getFetch;
exports.setFetch = setFetch;
