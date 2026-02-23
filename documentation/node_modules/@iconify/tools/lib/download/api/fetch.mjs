let customFetch = fetch;
function setFetch(fetchFunction) {
  customFetch = fetchFunction;
}
function getFetch() {
  return customFetch;
}

export { getFetch, setFetch };
