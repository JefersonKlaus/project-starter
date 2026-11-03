// In-memory stand-in for the browser WebSocket, driven manually from tests.
import type { SocketLike } from "@/lib/architect-socket";

export class FakeSocket implements SocketLike {
  static instances: FakeSocket[] = [];

  readonly url: string;
  readonly sent: unknown[] = [];
  readyState: number = WebSocket.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  static reset() {
    FakeSocket.instances = [];
  }

  static last(): FakeSocket {
    const s = FakeSocket.instances.at(-1);
    if (!s) throw new Error("No FakeSocket has been created yet");
    return s;
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (this.readyState !== WebSocket.OPEN) throw new Error("socket is not open");
    this.sent.push(JSON.parse(String(data)));
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  // ---- helpers used by tests to simulate the server ----
  open() {
    this.readyState = WebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  receive(message: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  receiveRaw(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  /** Simulates the server/network dropping the connection. */
  drop() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }
}
