'use strict';

const download_api_cache = require('./cache.cjs');
const download_api_config = require('./config.cjs');
const download_api_fetch = require('./fetch.cjs');
require('fs');
require('crypto');
require('../../misc/scan.cjs');

async function sendAPIQuery(query, cache) {
  const cacheKey = cache ? download_api_cache.apiCacheKey(query) : "";
  if (cache) {
    const cached = await download_api_cache.getAPICache(cache.dir, cacheKey);
    if (cached) {
      return cached;
    }
  }
  const result = await sendQuery(query);
  if (cache && typeof result !== "number") {
    try {
      await download_api_cache.storeAPICache(cache, cacheKey, result);
    } catch (err) {
      console.error("Error writing API cache");
    }
  }
  return result;
}
async function sendQuery(query) {
  const params = query.params ? query.params.toString() : "";
  const url = query.uri + (params ? "?" + params : "");
  const headers = query.headers;
  download_api_config.fetchCallbacks.onStart?.(url, query);
  function fail(value) {
    download_api_config.fetchCallbacks.onError?.(url, query, value);
    return value ?? 404;
  }
  const fetch = download_api_fetch.getFetch();
  try {
    const response = await fetch(url, {
      ...download_api_config.axiosConfig,
      headers
    });
    if (response.status !== 200) {
      return fail(response.status);
    }
    const data = await response.text();
    if (typeof data !== "string") {
      return fail();
    }
    download_api_config.fetchCallbacks.onSuccess?.(url, query);
    return data;
  } catch (err) {
    return fail();
  }
}

exports.sendAPIQuery = sendAPIQuery;
