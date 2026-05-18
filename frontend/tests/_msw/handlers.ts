import { HttpResponse, http } from "msw";
import appointments from "../fixtures/appointments.list.json";
import created from "../fixtures/entries.created.json";
import feeds from "../fixtures/feeds.list.json";
import poops from "../fixtures/poops.list.json";
import sleeps from "../fixtures/sleeps.list.json";

const base = "http://localhost:8000";

export const handlers = [
  http.get(`${base}/v1/feeds`, () => HttpResponse.json(feeds)),
  http.get(`${base}/v1/sleeps`, () => HttpResponse.json(sleeps)),
  http.get(`${base}/v1/poops`, () => HttpResponse.json(poops)),
  http.get(`${base}/v1/appointments`, () => HttpResponse.json(appointments)),
  http.post(`${base}/v1/entries`, () => HttpResponse.json(created)),
];
