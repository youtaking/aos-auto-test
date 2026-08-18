import { describe, test, expect, beforeEach } from "bun:test";

// ── Minimal EventEmitter copy for ACPState (based on packages/acp-link/src/client/emitter.ts) ──

class EventEmitter<TEvents extends Record<string, unknown>> {
  private _listeners = new Map<keyof TEvents, Set<(payload: any) => void>>();

  on<K extends keyof TEvents>(event: K, listener: (payload: TEvents[K]) => void): void {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, new Set());
    }
    this._listeners.get(event)!.add(listener);
  }

  off<K extends keyof TEvents>(event: K, listener: (payload: TEvents[K]) => void): void {
    this._listeners.get(event)?.delete(listener);
  }

  emit<K extends keyof TEvents>(event: K, payload: TEvents[K]): void {
    for (const listener of this._listeners.get(event) ?? []) {
      listener(payload);
    }
  }
}

// ── Type stubs ──

type ConnectionState = "connected" | "connecting" | "disconnected" | "error";

interface PromptCapabilities {
  image?: boolean;
  [key: string]: unknown;
}

interface SessionModelState {
  currentModelId: string;
  availableModels: Array<{ modelId: string; [key: string]: unknown }>;
}

interface SessionModeState {
  currentModeId: string;
  availableModes: Array<{ id: string; [key: string]: unknown }>;
}

interface AgentCapabilities {
  loadSession?: boolean;
  sessionCapabilities?: {
    resume?: unknown;
    list?: unknown;
  };
  [key: string]: unknown;
}

interface AvailableCommand {
  name: string;
  [key: string]: unknown;
}

interface StateEvents {
  connectionStateChange: { state: ConnectionState; error?: string };
  sessionIdChange: string | null;
  capabilitiesChange: AgentCapabilities | null;
  promptCapabilitiesChange: PromptCapabilities | null;
  modelStateChange: SessionModelState | null;
  modeStateChange: SessionModeState | null;
  availableCommandsChange: AvailableCommand[];
  [key: string]: unknown;
}

// ── ACPState pure class copy (state management only, no bind) ──

class ACPState extends EventEmitter<StateEvents> {
  private _connectionState: ConnectionState = "disconnected";
  private _sessionId: string | null = null;
  private _agentCapabilities: AgentCapabilities | null = null;
  private _promptCapabilities: PromptCapabilities | null = null;
  private _modelState: SessionModelState | null = null;
  private _modeState: SessionModeState | null = null;
  private _availableCommands: AvailableCommand[] = [];

  get connectionState(): ConnectionState { return this._connectionState; }
  get sessionId(): string | null { return this._sessionId; }
  get agentCapabilities(): AgentCapabilities | null { return this._agentCapabilities; }
  get promptCapabilities(): PromptCapabilities | null { return this._promptCapabilities; }
  get modelState(): SessionModelState | null { return this._modelState; }
  get modeState(): SessionModeState | null { return this._modeState; }
  get availableCommands(): AvailableCommand[] { return this._availableCommands; }

  get supportsImages(): boolean {
    return this._promptCapabilities?.image === true;
  }

  get supportsModelSelection(): boolean {
    return this._modelState !== null && this._modelState.availableModels.length > 0;
  }

  get supportsLoadSession(): boolean {
    return this._agentCapabilities?.loadSession === true;
  }

  get supportsResumeSession(): boolean {
    return (
      this._agentCapabilities?.sessionCapabilities?.resume !== undefined &&
      this._agentCapabilities?.sessionCapabilities?.resume !== null
    );
  }

  get supportsSessionList(): boolean {
    return (
      this._agentCapabilities?.sessionCapabilities?.list !== undefined &&
      this._agentCapabilities?.sessionCapabilities?.list !== null
    );
  }

  get supportsSessionHistory(): boolean {
    return this.supportsLoadSession || this.supportsResumeSession;
  }

  initSession(payload: {
    sessionId: string;
    promptCapabilities?: PromptCapabilities | null;
    models?: SessionModelState | null;
    modes?: SessionModeState | null;
  }): void {
    this._sessionId = payload.sessionId;
    this.emit("sessionIdChange", this._sessionId);
    this.setPromptCapabilities(payload.promptCapabilities ?? null);
    this.setModelState(payload.models ?? null);
    this.setModeState(payload.modes ?? null);
  }

  updateCurrentModel(modelId: string): void {
    if (!this._modelState) return;
    const availableIds = this._modelState.availableModels.map((m) => m.modelId);
    if (!availableIds.includes(modelId)) {
      console.warn(`[ACPState] updateCurrentModel: modelId "${modelId}" not in availableModels, skipping`);
      return;
    }
    this._modelState = { ...this._modelState, currentModelId: modelId };
    this.emit("modelStateChange", this._modelState);
  }

  updateCurrentMode(modeId: string): void {
    if (!this._modeState) return;
    const availableIds = this._modeState.availableModes.map((m) => m.id);
    if (!availableIds.includes(modeId)) {
      console.warn(`[ACPState] updateCurrentMode: modeId "${modeId}" not in availableModes, skipping`);
      return;
    }
    this._modeState = { ...this._modeState, currentModeId: modeId };
    this.emit("modeStateChange", this._modeState);
  }

  reset(): void {
    this.resetSessionState();
    this.setConnectionState("disconnected");
  }

  // ── Internal setters (exposed for testing since they affect getters) ──

  private setConnectionState(state: ConnectionState, error?: string): void {
    this._connectionState = state;
    this.emit("connectionStateChange", { state, error });
  }

  private setCapabilities(capabilities: AgentCapabilities | null): void {
    this._agentCapabilities = capabilities;
    this.emit("capabilitiesChange", capabilities);
  }

  private setPromptCapabilities(capabilities: PromptCapabilities | null): void {
    this._promptCapabilities = capabilities;
    this.emit("promptCapabilitiesChange", capabilities);
  }

  private setModelState(state: SessionModelState | null): void {
    this._modelState = state;
    this.emit("modelStateChange", state);
  }

  private setModeState(state: SessionModeState | null): void {
    this._modeState = state;
    this.emit("modeStateChange", state);
  }

  private resetSessionState(): void {
    this._sessionId = null;
    this._agentCapabilities = null;
    this._promptCapabilities = null;
    this._modelState = null;
    this._modeState = null;
    this._availableCommands = [];

    this.emit("sessionIdChange", null);
    this.emit("capabilitiesChange", null);
    this.emit("promptCapabilitiesChange", null);
    this.emit("modelStateChange", null);
    this.emit("modeStateChange", null);
    this.emit("availableCommandsChange", []);
  }
}

// ── Tests ──

describe("ACPState", () => {
  let state: ACPState;

  beforeEach(() => {
    state = new ACPState();
  });

  describe("initial state", () => {
    test("connectionState defaults to 'disconnected'", () => {
      expect(state.connectionState).toBe("disconnected");
    });

    test("sessionId defaults to null", () => {
      expect(state.sessionId).toBeNull();
    });

    test("agentCapabilities defaults to null", () => {
      expect(state.agentCapabilities).toBeNull();
    });

    test("promptCapabilities defaults to null", () => {
      expect(state.promptCapabilities).toBeNull();
    });

    test("modelState defaults to null", () => {
      expect(state.modelState).toBeNull();
    });

    test("modeState defaults to null", () => {
      expect(state.modeState).toBeNull();
    });

    test("availableCommands defaults to empty array", () => {
      expect(state.availableCommands).toEqual([]);
    });
  });

  describe("derived getters", () => {
    test("supportsImages is false when promptCapabilities is null", () => {
      expect(state.supportsImages).toBe(false);
    });

    test("supportsImages is true when image capability is true", () => {
      state.initSession({
        sessionId: "s1",
        promptCapabilities: { image: true },
      });
      expect(state.supportsImages).toBe(true);
    });

    test("supportsModelSelection is false when modelState is null", () => {
      expect(state.supportsModelSelection).toBe(false);
    });

    test("supportsModelSelection is false when no available models", () => {
      state.initSession({
        sessionId: "s1",
        models: { currentModelId: "m1", availableModels: [] },
      });
      expect(state.supportsModelSelection).toBe(false);
    });

    test("supportsModelSelection is true when models available", () => {
      state.initSession({
        sessionId: "s1",
        models: { currentModelId: "m1", availableModels: [{ modelId: "m1" }] },
      });
      expect(state.supportsModelSelection).toBe(true);
    });

    test("supportsLoadSession is false when capabilities is null", () => {
      expect(state.supportsLoadSession).toBe(false);
    });

    test("supportsResumeSession is false when capabilities is null", () => {
      expect(state.supportsResumeSession).toBe(false);
    });

    test("supportsSessionList is false when capabilities is null", () => {
      expect(state.supportsSessionList).toBe(false);
    });

    test("supportsSessionHistory combines loadSession and resumeSession", () => {
      expect(state.supportsSessionHistory).toBe(false);
    });

    test("supportsSessionHistory 当 loadSession 为 true 时返回 true", () => {
      (state as any).setCapabilities({ loadSession: true });
      expect(state.supportsSessionHistory).toBe(true);
    });

    test("supportsSessionHistory 当 resumeSession 为 true 时返回 true", () => {
      (state as any).setCapabilities({ sessionCapabilities: { resume: {} } });
      expect(state.supportsSessionHistory).toBe(true);
    });

    test("supportsSessionHistory 当两者都为 false 时返回 false", () => {
      (state as any).setCapabilities({ loadSession: false, sessionCapabilities: {} });
      expect(state.supportsLoadSession).toBe(false);
      expect(state.supportsResumeSession).toBe(false);
      expect(state.supportsSessionHistory).toBe(false);
    });
  });

  describe("initSession", () => {
    test("sets sessionId", () => {
      state.initSession({ sessionId: "session-123" });
      expect(state.sessionId).toBe("session-123");
    });

    test("emits sessionIdChange event", () => {
      let received: string | null = null;
      state.on("sessionIdChange", (v) => { received = v; });

      state.initSession({ sessionId: "session-456" });
      expect(received).toBe("session-456");
    });

    test("sets prompt capabilities", () => {
      state.initSession({
        sessionId: "s1",
        promptCapabilities: { image: true },
      });
      expect(state.promptCapabilities).toEqual({ image: true });
      expect(state.supportsImages).toBe(true);
    });

    test("sets model state", () => {
      const models = { currentModelId: "gpt-4", availableModels: [{ modelId: "gpt-4" }] };
      state.initSession({ sessionId: "s1", models });
      expect(state.modelState).toEqual(models);
    });

    test("sets mode state", () => {
      const modes = { currentModeId: "chat", availableModes: [{ id: "chat" }] };
      state.initSession({ sessionId: "s1", modes });
      expect(state.modeState).toEqual(modes);
    });

    test("null payload fields default to null", () => {
      state.initSession({ sessionId: "s1" });
      expect(state.promptCapabilities).toBeNull();
      expect(state.modelState).toBeNull();
      expect(state.modeState).toBeNull();
    });

    test("initSession 重复调用覆盖旧值", () => {
      state.initSession({
        sessionId: "session-first",
        promptCapabilities: { image: true },
        models: { currentModelId: "m1", availableModels: [{ modelId: "m1" }] },
      });
      expect(state.sessionId).toBe("session-first");
      expect(state.supportsImages).toBe(true);
      expect(state.modelState?.currentModelId).toBe("m1");

      // 第二次调用覆盖 sessionId 和 promptCapabilities，models 缺省为 null
      state.initSession({
        sessionId: "session-second",
        promptCapabilities: { image: false },
      });
      expect(state.sessionId).toBe("session-second");
      expect(state.supportsImages).toBe(false);
      expect(state.modelState).toBeNull();
    });
  });

  describe("updateCurrentModel", () => {
    test("updates currentModelId when model is in available list", () => {
      state.initSession({
        sessionId: "s1",
        models: {
          currentModelId: "m1",
          availableModels: [{ modelId: "m1" }, { modelId: "m2" }],
        },
      });

      state.updateCurrentModel("m2");
      expect(state.modelState?.currentModelId).toBe("m2");
    });

    test("emits modelStateChange event on valid update", () => {
      state.initSession({
        sessionId: "s1",
        models: {
          currentModelId: "m1",
          availableModels: [{ modelId: "m1" }, { modelId: "m2" }],
        },
      });

      let received: SessionModelState | null = null;
      state.on("modelStateChange", (v) => { received = v; });

      state.updateCurrentModel("m2");
      expect(received?.currentModelId).toBe("m2");
    });

    test("rejects modelId not in availableModels", () => {
      state.initSession({
        sessionId: "s1",
        models: {
          currentModelId: "m1",
          availableModels: [{ modelId: "m1" }],
        },
      });

      state.updateCurrentModel("m-invalid");
      expect(state.modelState?.currentModelId).toBe("m1");
    });

    test("no-op when modelState is null", () => {
      // Should not throw
      state.updateCurrentModel("any");
      expect(state.modelState).toBeNull();
    });
  });

  describe("updateCurrentMode", () => {
    test("updates currentModeId when mode is in available list", () => {
      state.initSession({
        sessionId: "s1",
        modes: {
          currentModeId: "chat",
          availableModes: [{ id: "chat" }, { id: "code" }],
        },
      });

      state.updateCurrentMode("code");
      expect(state.modeState?.currentModeId).toBe("code");
    });

    test("rejects modeId not in availableModes", () => {
      state.initSession({
        sessionId: "s1",
        modes: {
          currentModeId: "chat",
          availableModes: [{ id: "chat" }],
        },
      });

      state.updateCurrentMode("invalid");
      expect(state.modeState?.currentModeId).toBe("chat");
    });

    test("no-op when modeState is null", () => {
      state.updateCurrentMode("any");
      expect(state.modeState).toBeNull();
    });
  });

  describe("reset", () => {
    test("resets all state to defaults", () => {
      state.initSession({
        sessionId: "s1",
        promptCapabilities: { image: true },
        models: { currentModelId: "m1", availableModels: [{ modelId: "m1" }] },
        modes: { currentModeId: "chat", availableModes: [{ id: "chat" }] },
      });

      state.reset();

      expect(state.sessionId).toBeNull();
      expect(state.promptCapabilities).toBeNull();
      expect(state.modelState).toBeNull();
      expect(state.modeState).toBeNull();
      expect(state.availableCommands).toEqual([]);
      expect(state.connectionState).toBe("disconnected");
    });

    test("emits reset events", () => {
      state.initSession({ sessionId: "s1" });

      const events: string[] = [];
      state.on("sessionIdChange", () => events.push("sessionId"));
      state.on("capabilitiesChange", () => events.push("capabilities"));
      state.on("connectionStateChange", () => events.push("connection"));

      state.reset();

      expect(events).toContain("sessionId");
      expect(events).toContain("capabilities");
      expect(events).toContain("connection");
    });
  });
});
