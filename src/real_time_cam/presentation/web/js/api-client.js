// @ts-check
/**
 * Typed HTTP client for the XeroxUAV FastAPI configuration endpoints.
 * Uses relative URLs so the page works across any LAN hostname or IP.
 */

export const BOOTSTRAP_CONFIG_URL = "./api/v1/config";

/**
 * @typedef {Object} MediaMtxPlaybackInfo
 * @property {string} public_host
 * @property {number} webrtc_http_port
 * @property {string} stream_path
 * @property {string} whep_path
 */

/**
 * @typedef {Object} StreamConfigInfo
 * @property {string} resolution
 * @property {number} fps_hz
 * @property {number} bitrate_kbps
 * @property {string} encoder_kind
 */

/**
 * @typedef {Object} BackendBootstrapPayload
 * @property {MediaMtxPlaybackInfo} mediamtx
 * @property {StreamConfigInfo} stream
 */

/**
 * Fetch initial MediaMTX and stream configuration from the FastAPI backend.
 * Returns `null` when the static page is opened without the FastAPI server.
 *
 * @returns {Promise<BackendBootstrapPayload | null>}
 */
export async function fetchBackendBootstrap() {
  try {
    const response = await globalThis.fetch(BOOTSTRAP_CONFIG_URL, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    return /** @type {Promise<BackendBootstrapPayload>} */ (response.json());
  } catch {
    return null;
  }
}
