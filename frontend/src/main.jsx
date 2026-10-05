import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, clearToken, setToken, token } from "./api.js";
import "./app.css";

const STATUS_LABEL = { soaking: "浸茧", reeling: "缫丝中", reeled: "已缫完" };

function Login({ onOk }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(data.access_token);
      onOk();
    } catch (ex) {
      setErr(ex.message);
    }
  }
  return (
    <div class="login">
      <h1>江口缫丝坞</h1>
      <p>汤温环盆作业台，不是列表台账。</p>
      <form onSubmit={submit} autocomplete="off">
        <label>
          用户名
          <input name="username" autocomplete="off" value={username} onInput={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          密码
          <input name="password" type="password" autocomplete="off" value={password} onInput={(e) => setPassword(e.target.value)} />
        </label>
        <p class="hint">已预填 admin / 123456，另有 worker / 123456</p>
        <button type="submit">登录</button>
      </form>
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function TopBar({ view, onNav }) {
  return (
    <div class="topbar">
      <nav class="navtabs">
        <button class={view === "yard" ? "navtab active" : "navtab"} onClick={() => onNav("yard")}>
          环盆作业台
        </button>
        <button
          class={view === "counter" ? "navtab active" : "navtab"}
          onClick={() => onNav("counter")}
        >
          已缫完次数台
        </button>
      </nav>
      <button
        class="logout"
        onClick={() => {
          clearToken();
          location.reload();
        }}
      >
        退出
      </button>
    </div>
  );
}

function Yard({ onNav }) {
  const [board, setBoard] = useState(null);
  const [picked, setPicked] = useState(null);
  const [temp, setTemp] = useState("40");
  const [err, setErr] = useState("");

  async function refresh() {
    const data = await api("/api/board");
    setBoard(data);
    if (picked) {
      setPicked(data.basins.find((b) => b.id === picked.id) || data.basins[0]);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  if (!board) {
    return (
      <div class="yard">
        <TopBar view="yard" onNav={onNav} />
        {err || "装载环盆…"}
      </div>
    );
  }

  const n = board.basins.length;
  async function writeTemp() {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/readings`, {
        method: "POST",
        body: JSON.stringify({ waterTempC: Number(temp) }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }
  async function setStatus(status) {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div class="yard">
      <TopBar view="yard" onNav={onNav} />
      <div class="subtitle">
        <h1>{board.filature}</h1>
        <p>{board.riverside} · 点盆登记汤温；已缫完须最近汤温 38～42℃</p>
      </div>
      <div class="ring">
        {board.basins.map((b, i) => {
          const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
          const left = 50 + Math.cos(angle) * 38;
          const top = 50 + Math.sin(angle) * 38;
          return (
            <button
              key={b.id}
              class={`basin ${b.status}`}
              style={{ left: `${left}%`, top: `${top}%` }}
              onClick={() => setPicked(b)}
            >
              <strong>{b.code}</strong>
              <span>{STATUS_LABEL[b.status]}</span>
            </button>
          );
        })}
      </div>
      {picked && (
        <div class="drawer">
          <h3>
            {picked.code} · {STATUS_LABEL[picked.status]}
          </h3>
          <p>最近汤温：{picked.latestTempC ?? "无"} ℃ · 记录 {picked.readingCount} 次</p>
          <input value={temp} onInput={(e) => setTemp(e.target.value)} />
          <button onClick={writeTemp}>登记汤温</button>
          <div>
            <button onClick={() => setStatus("soaking")}>浸茧</button>
            <button onClick={() => setStatus("reeling")}>缫丝中</button>
            <button onClick={() => setStatus("reeled")}>已缫完</button>
          </div>
          {err && <p class="err">{err}</p>}
        </div>
      )}
    </div>
  );
}

function ReeledCounter({ onNav }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  async function refresh() {
    setErr("");
    try {
      setData(await api("/api/counters/reeled-today"));
    } catch (ex) {
      setErr(ex.message);
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div class="counter-page">
      <TopBar view="counter" onNav={onNav} />
      <div class="counter-card">
        <h1>已缫完次数台</h1>
        <p class="counter-date">服务器自然日 · {data ? data.date : "—"}</p>
        <div class="counter-number">{data ? data.reeledCount : "—"}</div>
        <p class="counter-note">
          今日成功把盆态改成「已缫完」的次数。一口盆同一轮缫丝只计一次；
          本页只读，不能改态、不能登记汤温。
        </p>
        <button onClick={refresh}>刷新</button>
        {err && <p class="err">{err}</p>}
      </div>
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(Boolean(token()));
  const [view, setView] = useState("yard");
  if (!ready) {
    return <Login onOk={() => setReady(true)} />;
  }
  return view === "counter" ? (
    <ReeledCounter onNav={setView} />
  ) : (
    <Yard onNav={setView} />
  );
}

render(<App />, document.getElementById("app"));
