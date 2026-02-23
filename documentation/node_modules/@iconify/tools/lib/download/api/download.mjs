import { writeFile } from 'fs/promises';
import { fetchCallbacks, axiosConfig } from './config.mjs';
import { getFetch } from './fetch.mjs';

async function downloadFile(query, target) {
  const params = query.params ? query.params.toString() : "";
  const url = query.uri + (params ? "?" + params : "");
  const headers = query.headers;
  fetchCallbacks.onStart?.(url, query);
  const fetch = getFetch();
  const response = await fetch(url, {
    ...axiosConfig,
    headers
  });
  if (response.status !== 200) {
    fetchCallbacks.onError?.(url, query, response.status);
    throw new Error(`Error downloading ${url}: ${response.status}`);
  }
  const data = await response.arrayBuffer();
  fetchCallbacks.onSuccess?.(url, query);
  await writeFile(target, Buffer.from(data));
}

export { downloadFile };
