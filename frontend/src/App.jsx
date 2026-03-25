import { useEffect, useRef, useState } from "react";

const EMPTY_FORM = {
  heroBuyin: 50,
  revealAll: false,
};

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [sessionId, setSessionId] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [raiseSize, setRaiseSize] = useState("");
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!snapshot?.legal_actions) {
      return;
    }
    if (snapshot.legal_actions.min_raise_to_bb != null) {
      setRaiseSize(String(snapshot.legal_actions.min_raise_to_bb));
    } else {
      setRaiseSize("");
    }
  }, [snapshot?.hand_number, snapshot?.actor_index, snapshot?.legal_actions?.min_raise_to_bb]);

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  async function createSession(event) {
    event.preventDefault();
    setError("");
    setConnecting(true);

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hero_buyin_bb: Number(form.heroBuyin),
        reveal_all_cards_after_hand: form.revealAll,
      }),
    });

    if (!response.ok) {
      setConnecting(false);
      setError("Could not create a session.");
      return;
    }

    const payload = await response.json();
    setSessionId(payload.session_id);
    setSnapshot(payload.snapshot);
    connectSocket(payload.session_id);
  }

  function connectSocket(id) {
    socketRef.current?.close();
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/session/${id}`);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "error") {
        setError(message.message);
        return;
      }
      if (message.type === "state") {
        setSnapshot(message.payload);
        setError("");
      }
    };

    socket.onopen = () => setConnecting(false);
    socket.onclose = () => setConnecting(false);
  }

  function sendAction(action, amountBb = null) {
    if (!socketRef.current) {
      return;
    }
    setError("");
    socketRef.current.send(
      JSON.stringify({
        type: "action",
        action,
        amount_bb: amountBb == null ? undefined : Number(amountBb),
      }),
    );
  }

  function sendNextHand() {
    socketRef.current?.send(JSON.stringify({ type: "next_hand" }));
  }

  return (
    <main className="app-shell">
      <header className="hero-banner">
        <div>
          <p className="eyebrow">V1 Local Simulator</p>
          <h1>Poker Simulator</h1>
          <p className="subtitle">
            Play repeated 6-max cash-game hands against strong heuristic bots.
          </p>
        </div>
        <div className="status-card">
          <span>Transport</span>
          <strong>{sessionId ? "WebSocket live" : "Not connected"}</strong>
          {sessionId ? <small>Session {sessionId.slice(0, 8)}</small> : null}
        </div>
      </header>

      {!sessionId ? (
        <section className="panel setup-panel">
          <h2>Start a Session</h2>
          <form className="setup-form" onSubmit={createSession}>
            <label>
              Hero Buy-In (10-100bb)
              <input
                type="number"
                min="10"
                max="100"
                value={form.heroBuyin}
                onChange={(event) =>
                  setForm((current) => ({ ...current, heroBuyin: event.target.value }))
                }
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.revealAll}
                onChange={(event) =>
                  setForm((current) => ({ ...current, revealAll: event.target.checked }))
                }
              />
              Reveal all hole cards after each hand
            </label>
            <button className="primary-button" type="submit" disabled={connecting}>
              {connecting ? "Starting..." : "Create Table"}
            </button>
          </form>
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      ) : null}

      {snapshot ? (
        <section className="table-layout">
          <div className="table-surface">
            <div className="table-meta">
              <div>
                <span>Hand</span>
                <strong>#{snapshot.hand_number}</strong>
              </div>
              <div>
                <span>Street</span>
                <strong>{snapshot.street.toUpperCase()}</strong>
              </div>
              <div>
                <span>Pot</span>
                <strong>{snapshot.pot_bb}bb</strong>
              </div>
            </div>

            <div className="board-row">
              {snapshot.board.length ? snapshot.board.map((card) => <CardView key={card} card={card} />) : <span className="muted-copy">Waiting for the board...</span>}
            </div>

            <div className="seat-grid">
              {snapshot.seats.map((seat) => (
                <article
                  key={seat.seat_index}
                  className={`seat-card ${seat.acting ? "acting" : ""} ${seat.folded ? "folded" : ""} ${seat.is_human ? "hero-seat" : ""}`}
                >
                  <div className="seat-topline">
                    <strong>{seat.name}</strong>
                    <span>{seat.position}</span>
                  </div>
                  <p>{seat.stack_bb}bb</p>
                  <p className="seat-commit">Committed: {seat.committed_bb}bb</p>
                  <div className="cards-row">
                    {seat.cards ? seat.cards.map((card) => <CardView key={`${seat.seat_index}-${card}`} card={card} />) : <HiddenCards />}
                  </div>
                  {seat.all_in ? <span className="seat-chip all-in">All-in</span> : null}
                  {seat.folded ? <span className="seat-chip folded-chip">Folded</span> : null}
                </article>
              ))}
            </div>
          </div>

          <aside className="sidebar">
            <section className="panel">
              <h2>Action</h2>
              {snapshot.hand_complete ? (
                <>
                  <p>{snapshot.hand_result?.summary}</p>
                  <p>Rake: {snapshot.hand_result?.rake_bb ?? 0}bb</p>
                  <button className="primary-button" type="button" onClick={sendNextHand}>
                    Next Hand
                  </button>
                </>
              ) : snapshot.legal_actions ? (
                <div className="actions-panel">
                  {snapshot.legal_actions.can_fold ? (
                    <button type="button" onClick={() => sendAction("fold")}>
                      Fold
                    </button>
                  ) : null}
                  {snapshot.legal_actions.can_check ? (
                    <button type="button" onClick={() => sendAction("check")}>
                      Check
                    </button>
                  ) : null}
                  {snapshot.legal_actions.call_amount_bb > 0 ? (
                    <button type="button" onClick={() => sendAction("call")}>
                      Call {snapshot.legal_actions.call_amount_bb}bb
                    </button>
                  ) : null}
                  {snapshot.legal_actions.min_raise_to_bb != null ? (
                    <>
                      <label>
                        Bet / Raise To
                        <input
                          type="number"
                          step="0.1"
                          min={snapshot.legal_actions.min_raise_to_bb}
                          max={snapshot.legal_actions.max_raise_to_bb}
                          value={raiseSize}
                          onChange={(event) => setRaiseSize(event.target.value)}
                        />
                      </label>
                      <div className="action-row">
                        <button type="button" onClick={() => sendAction(snapshot.current_bet_bb > 0 ? "raise_to" : "bet", raiseSize)}>
                          {snapshot.current_bet_bb > 0 ? "Raise" : "Bet"}
                        </button>
                        <button type="button" onClick={() => sendAction("all_in")}>
                          All-In
                        </button>
                      </div>
                    </>
                  ) : (
                    <button type="button" onClick={() => sendAction("all_in")}>
                      All-In
                    </button>
                  )}
                </div>
              ) : (
                <p className="muted-copy">Bots are acting...</p>
              )}
              {error ? <p className="error-text">{error}</p> : null}
            </section>

            <section className="panel">
              <h2>Recent Actions</h2>
              <ul className="history-list">
                {snapshot.action_history.length ? (
                  snapshot.action_history
                    .slice()
                    .reverse()
                    .map((item, index) => (
                      <li key={`${item.player_name}-${item.street}-${index}`}>
                        <strong>{item.player_name}</strong>{" "}
                        <span>
                          {item.action_type}
                          {item.amount_bb != null ? ` to ${item.amount_bb}bb` : ""}
                        </span>
                      </li>
                    ))
                ) : (
                  <li>No actions yet.</li>
                )}
              </ul>
            </section>
          </aside>
        </section>
      ) : null}
    </main>
  );
}

function CardView({ card }) {
  const red = card.endsWith("h") || card.endsWith("d");
  return <span className={`card-tile ${red ? "red" : ""}`}>{card}</span>;
}

function HiddenCards() {
  return (
    <>
      <span className="card-tile hidden">?</span>
      <span className="card-tile hidden">?</span>
    </>
  );
}
