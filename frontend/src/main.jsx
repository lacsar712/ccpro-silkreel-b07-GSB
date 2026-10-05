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

function TopBar({ page, onNav, title, sub }) {
  return (
    <div class="topbar">
      <div>
        <h1>{title}</h1>
        <p>{sub}</p>
        <nav class="tabs">
          <button class={page === "yard" ? "on" : ""} onClick={() => onNav("yard")}>
            环盆作业台
          </button>
          <button class={page === "count" ? "on" : ""} onClick={() => onNav("count")}>
            已缫完次数台
          </button>
        </nav>
      </div>
      <button
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
      <TopBar
        page="yard"
        onNav={onNav}
        title={board.filature}
        sub={`${board.riverside} · 点盆登记汤温；已缫完须最近汤温 38～42℃`}
      />
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

function ReeledCount({ onNav }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  async function load() {
    try {
      setData(await api("/api/reeled-count/today"));
      setErr("");
    } catch (ex) {
      setErr(ex.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div class="yard">
      <TopBar
        page="count"
        onNav={onNav}
        title="已缫完次数台"
        sub="只统计今天（服务器自然日）成功把盆态改成已缫完的次数"
      />
      {err && <p class="err">{err}</p>}
      {!data ? (
        <p>装载次数台…</p>
      ) : (
        <div>
          <div class="countcard">
            <div class="bignum">{data.count}</div>
            <p>今日 {data.day} 成功标定已缫完次数</p>
          </div>
          <button onClick={load}>刷新</button>
          {data.events.length > 0 && (
            <table class="events">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>盆位</th>
                  <th>工人</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((ev, i) => (
                  <tr key={i}>
                    <td>{ev.happenedAt ? new Date(ev.happenedAt).toLocaleString() : "—"}</td>
                    <td>{ev.basinCode}</td>
                    <td>{ev.operator}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p class="hint">本页只读：不能改盆态、不能登记汤温；改态请去「环盆作业台」。</p>
        </div>
      )}
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(Boolean(token()));
  const [page, setPage] = useState("yard");
  if (!ready) {
    return <Login onOk={() => setReady(true)} />;
  }
  return page === "count" ? <ReeledCount onNav={setPage} /> : <Yard onNav={setPage} />;
}

render(<App />, document.getElementById("app"));
