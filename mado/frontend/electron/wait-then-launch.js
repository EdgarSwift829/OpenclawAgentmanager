/**
 * Wait for Next.js dev server to be ready, then launch Electron.
 */
const http = require("http");
const { spawn } = require("child_process");

const URL = "http://localhost:3000";
const MAX_RETRIES = 30;
const INTERVAL_MS = 1000;

let attempts = 0;

function check() {
  attempts++;
  http
    .get(URL, (res) => {
      if (res.statusCode === 200 || res.statusCode === 304) {
        console.log("[MADO] Next.js ready — launching Electron...");
        const electron = require("electron");
        const child = spawn(electron, ["."], {
          cwd: require("path").join(__dirname, ".."),
          stdio: "inherit",
        });
        child.on("close", () => process.exit());
      } else {
        retry();
      }
    })
    .on("error", retry);
}

function retry() {
  if (attempts >= MAX_RETRIES) {
    console.error("[MADO] Next.js did not start in time. Aborting.");
    process.exit(1);
  }
  setTimeout(check, INTERVAL_MS);
}

console.log("[MADO] Waiting for Next.js dev server...");
check();
