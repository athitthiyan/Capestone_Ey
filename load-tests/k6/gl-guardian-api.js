import http from "k6/http";
import { check, group, sleep } from "k6";
import { Counter, Rate } from "k6/metrics";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const API_PREFIX = __ENV.API_PREFIX || "/api/v1";
const TOKEN = __ENV.TOKEN || "";
const WRITE_CASES = (__ENV.WRITE_CASES || "false").toLowerCase() === "true";
const PROFILE = (__ENV.PROFILE || "baseline").toLowerCase();

const failures = new Rate("gl_guardian_failed_checks");
const createdCases = new Counter("gl_guardian_created_cases");

const profiles = {
  smoke: {
    vus: 1,
    duration: "30s",
    thresholds: {
      http_req_failed: ["rate<0.01"],
      http_req_duration: ["p(95)<750"],
      gl_guardian_failed_checks: ["rate<0.01"],
    },
  },
  baseline: {
    stages: [
      { duration: "30s", target: 5 },
      { duration: "2m", target: 5 },
      { duration: "30s", target: 0 },
    ],
    thresholds: {
      http_req_failed: ["rate<0.02"],
      http_req_duration: ["p(95)<1000"],
      gl_guardian_failed_checks: ["rate<0.02"],
    },
  },
  presentation: {
    stages: [
      { duration: "30s", target: 10 },
      { duration: "3m", target: 10 },
      { duration: "1m", target: 25 },
      { duration: "30s", target: 0 },
    ],
    thresholds: {
      http_req_failed: ["rate<0.03"],
      http_req_duration: ["p(95)<1500"],
      gl_guardian_failed_checks: ["rate<0.03"],
    },
  },
  stress: {
    stages: [
      { duration: "1m", target: 20 },
      { duration: "2m", target: 50 },
      { duration: "2m", target: 100 },
      { duration: "1m", target: 0 },
    ],
    thresholds: {
      http_req_failed: ["rate<0.05"],
      http_req_duration: ["p(95)<2500"],
      gl_guardian_failed_checks: ["rate<0.05"],
    },
  },
};

const selected = profiles[PROFILE] || profiles.baseline;

export const options = {
  scenarios: {
    api_read_path: {
      executor: "ramping-vus",
      stages: selected.stages || [
        { duration: selected.duration || "30s", target: selected.vus || 1 },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: selected.thresholds,
};

function headers() {
  const result = {
    "Content-Type": "application/json",
  };
  if (TOKEN) {
    result.Authorization = `Bearer ${TOKEN}`;
  }
  return result;
}

function api(path) {
  return `${BASE_URL}${API_PREFIX}${path}`;
}

function mark(name, response, predicate) {
  const ok = check(response, {
    [name]: predicate,
  });
  failures.add(!ok);
  return ok;
}

function readPath() {
  group("read path", () => {
    let response = http.get(`${BASE_URL}/health`, { tags: { endpoint: "health" } });
    mark("health is 200", response, (r) => r.status === 200);

    response = http.get(api("/investigations?limit=25"), {
      headers: headers(),
      tags: { endpoint: "investigations_list" },
    });
    mark("investigations list is 200", response, (r) => r.status === 200);

    response = http.get(api("/analytics/kpis"), {
      headers: headers(),
      tags: { endpoint: "analytics_kpis" },
    });
    mark("analytics kpis is 200", response, (r) => r.status === 200);

    response = http.get(api("/analytics/trend?limit=500"), {
      headers: headers(),
      tags: { endpoint: "analytics_trend" },
    });
    mark("analytics trend is 200", response, (r) => r.status === 200);
  });
}

function writePath() {
  group("write path", () => {
    const unique = `${Date.now()}-${__VU}-${__ITER}`;
    const body = JSON.stringify({
      transaction_id: `LT-${unique}`,
      vendor: `Load Test Vendor ${__VU}`,
      category: "load-test",
      amount: 75000 + __ITER,
      materiality: 50000,
      owner: "load-test",
      description: "Synthetic load-test case. Do not use for audit conclusions.",
    });

    const response = http.post(api("/investigations"), body, {
      headers: headers(),
      tags: { endpoint: "investigations_create" },
    });
    const ok = mark("create investigation is 201", response, (r) => r.status === 201);
    if (ok) {
      createdCases.add(1);
    }
  });
}

export default function () {
  readPath();
  if (WRITE_CASES) {
    writePath();
  }
  sleep(Math.random() * 2 + 1);
}
