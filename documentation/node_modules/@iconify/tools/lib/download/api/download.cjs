'use strict';

const promises = require('fs/promises');
const download_api_config = require('./config.cjs');
const download_api_fetch = require('./fetch.cjs');

async function downloadFile(query, target) {
  const params = query.params ? query.params.toString() : "";
  const url = query.uri + (params ? "?" + params : "");
  const headers = query.headers;
  download_api_config.fetchCallbacks.onStart?.(url, query);
  const fetch = download_api_fetch.getFetch();
  const response = await fetch(url, {
    ...download_api_config.axiosConfig,
    headers
  });
  if (response.status !== 200) {
    download_api_config.fetchCallbacks.onError?.(url, query, response.status);
    throw new Error(`Error downloading ${url}: ${response.status}`);
  }
  const data = await response.arrayBuffer();
  download_api_config.fetchCallbacks.onSuccess?.(url, query);
  await promises.writeFile(target, Buffer.from(data));
}

exports.downloadFile = downloadFile;
