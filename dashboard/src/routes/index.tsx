import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  CarFront,
  ChevronDown,
  Clock3,
  LayoutDashboard,
  Menu,
  RefreshCw,
  RouteIcon,
  Settings,
  TrafficCone,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import logoUrl from "@/assets/siat-logo.png";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Visão geral | SIAT" },
      { name: "description", content: "Painel operacional do Sistema Inteligente Adaptativo de Tráfego." },
      { property: "og:title", content: "Visão geral | SIAT" },
      { property: "og:description", content: "Painel operacional do Sistema Inteligente Adaptativo de Tráfego." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type TimePoint = { timestamp: string; tempo_via1: number; tempo_via2: number };
type Detection = { timestamp: string; via: string; quantidade_carros: number };
type StatusEsp32 = {
  conectado: boolean;
  segundos_desde_contato: number | null;
  ultimo_contato: string | null;
  ip: string | null;
  limite_segundos: number;
};
type PorHora = {
  hora: string;
  carros_via1: number;
  carros_via2: number;
  razao_via1: number;
  razao_via2: number;
  aberto_via1: number;
  aberto_via2: number;
};
type Conexao = "carregando" | "conectado" | "desconectado" | "servidor_offline";

const navItems = [
  { label: "Visão geral", icon: LayoutDashboard },
  { label: "Cruzamentos", icon: TrafficCone },
  { label: "Fluxo viário", icon: RouteIcon },
  { label: "Relatórios", icon: Activity },
];

// Aparência de cada estado de conexão (cores do próprio tema do dashboard)
const conexaoInfo: Record<Conexao, { titulo: string; pill: string; ponto: string; pulso: boolean }> = {
  carregando: { titulo: "Verificando conexão", pill: "bg-secondary text-secondary-foreground", ponto: "bg-muted-foreground", pulso: false },
  conectado: { titulo: "Semáforos conectados", pill: "bg-accent text-accent-foreground", ponto: "bg-signal-green", pulso: true },
  desconectado: { titulo: "Semáforos desconectados", pill: "bg-signal-red/10 text-signal-red", ponto: "bg-signal-red", pulso: false },
  servidor_offline: { titulo: "Servidor offline", pill: "bg-signal-red/10 text-signal-red", ponto: "bg-signal-red", pulso: false },
};

function formatTime(timestamp: string) {
  return timestamp.includes("T") || timestamp.length > 8 ? timestamp.slice(11, 16) : timestamp;
}

// Busca uma rota do servidor; devolve null se o servidor não responder ou der erro
async function buscar<T>(url: string): Promise<T | null> {
  try {
    const resposta = await fetch(url);
    return resposta.ok ? ((await resposta.json()) as T) : null;
  } catch {
    return null;
  }
}

function descreverContato(segundos: number | null) {
  if (segundos === null) return "Nenhum contato recebido ainda";
  if (segundos < 60) return `Último contato há ${segundos} s`;
  if (segundos < 3600) return `Último contato há ${Math.floor(segundos / 60)} min`;
  return `Último contato há ${Math.floor(segundos / 3600)} h`;
}

function Index() {
  const [times, setTimes] = useState<TimePoint[]>([]);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [status, setStatus] = useState<StatusEsp32 | null>(null);
  const [porHora, setPorHora] = useState<PorHora[]>([]);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [updatedAt, setUpdatedAt] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const updateData = useCallback(async () => {
    setRefreshing(true);

    const [timeData, detectionData, statusData, hourData] = await Promise.all([
      buscar<TimePoint[]>("/dados/tempos"),
      buscar<Detection[]>("/dados/deteccoes"),
      buscar<StatusEsp32>("/dados/status"),
      buscar<PorHora[]>("/dados/por-hora"),
    ]);

    // Se nenhuma rota respondeu, o servidor Flask está fora do ar
    const online = [timeData, detectionData, statusData, hourData].some((resposta) => resposta !== null);
    setServerOnline(online);

    if (timeData) setTimes([...timeData].reverse().slice(-30));
    if (detectionData) setDetections([...detectionData].reverse().slice(-30));
    if (statusData) setStatus(statusData);
    if (hourData) setPorHora(hourData);
    if (online) setUpdatedAt(new Date());

    setRefreshing(false);
  }, []);

  useEffect(() => {
    void updateData();
    const timer = window.setInterval(() => void updateData(), 5000);

    // Navegadores desaceleram o setInterval em abas fora de foco. Isso faz o dashboard
    // buscar dados imediatamente assim que a aba volta a ficar visível, em vez de esperar
    // o próximo tick do timer (que pode demorar bem mais que 5s depois de ficar em segundo plano).
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void updateData();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [updateData]);

  // Estado de conexão: primeiro vê se o servidor responde, depois se o ESP32 está em contato com ele
  const conexao: Conexao =
    serverOnline === null ? "carregando" : !serverOnline ? "servidor_offline" : status?.conectado ? "conectado" : "desconectado";
  const info = conexaoInfo[conexao];
  const conectado = conexao === "conectado";

  const chartTimes = useMemo(() => times.map((item) => ({ ...item, hora: formatTime(item.timestamp) })), [times]);
  const chartDetections = useMemo(() => detections.map((item) => ({ ...item, hora: formatTime(item.timestamp) })), [detections]);
  const chartPorHora = useMemo(
    () =>
      porHora.map((item) => ({
        ...item,
        rotulo: `${item.hora.slice(11, 13)}h`,
        pct_via1: Math.round(item.razao_via1 * 100),
        pct_via2: Math.round(item.razao_via2 * 100),
        min_via1: Math.round((item.aberto_via1 / 60) * 10) / 10,
        min_via2: Math.round((item.aberto_via2 / 60) * 10) / 10,
      })),
    [porHora],
  );
  const latest = times.at(-1);
  const totalCars = detections.reduce((sum, item) => sum + item.quantidade_carros, 0);

  const valorConexao = { carregando: "…", conectado: "Conectado", desconectado: "Desconectado", servidor_offline: "Sem servidor" }[conexao];
  const detalheConexao =
    conexao === "servidor_offline"
      ? "Sem resposta do servidor"
      : conexao === "carregando"
        ? "Consultando o servidor"
        : descreverContato(status?.segundos_desde_contato ?? null);

  const detalheEsp32 =
    conexao === "servidor_offline"
      ? "Não foi possível consultar o servidor"
      : [
          descreverContato(status?.segundos_desde_contato ?? null),
          status?.ultimo_contato ? `às ${status.ultimo_contato.slice(11, 19)}` : null,
          status?.ip ? `IP ${status.ip}` : null,
        ]
          .filter(Boolean)
          .join(" • ");
  const estadoEsp32 = { carregando: "Verificando", conectado: "Conectado", desconectado: "Desconectado", servidor_offline: "Sem informação" }[conexao];

  return (
    <div className="min-h-screen bg-background text-foreground lg:grid lg:grid-cols-[258px_minmax(0,1fr)]">
      {menuOpen && <button aria-label="Fechar menu" className="fixed inset-0 z-30 bg-surface-strong/40 lg:hidden" onClick={() => setMenuOpen(false)} />}

      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[258px] flex-col bg-sidebar text-sidebar-foreground transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen ${menuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
        <div className="flex h-24 items-center border-b border-sidebar-border px-6">
          <div className="rounded-md bg-card px-3 py-2">
            <img src={logoUrl} alt="SIAT — Sistema Inteligente Adaptativo de Tráfego" className="h-11 w-40 object-contain" />
          </div>
          <Button variant="ghost" size="icon" className="ml-auto text-sidebar-foreground lg:hidden" onClick={() => setMenuOpen(false)} aria-label="Fechar menu"><X /></Button>
        </div>

        <nav className="flex-1 px-4 py-7" aria-label="Navegação principal">
          <p className="mb-3 px-3 text-[11px] font-bold uppercase tracking-[0.16em] text-sidebar-foreground/50">Monitoramento</p>
          <div className="space-y-1">
            {navItems.map(({ label, icon: Icon }, index) => (
              <button key={label} className={`flex h-11 w-full items-center gap-3 rounded-md px-3 text-left text-sm font-semibold transition-colors ${index === 0 ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/65 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"}`}>
                <Icon className={index === 0 ? "text-signal-green" : ""} size={19} />{label}
              </button>
            ))}
          </div>
        </nav>

        <div className="border-t border-sidebar-border p-4">
          <button className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-sm font-semibold text-sidebar-foreground/65 hover:bg-sidebar-accent hover:text-sidebar-foreground"><Settings size={18} />Configurações</button>
          <div className="mt-3 flex items-center gap-3 border-t border-sidebar-border px-3 pt-5">
            <div className="flex size-9 items-center justify-center rounded-full bg-signal-green font-display text-sm font-bold text-primary-foreground">OP</div>
            <div className="min-w-0"><p className="truncate text-sm font-semibold">Central de Operações</p><p className="text-xs text-sidebar-foreground/50">Operador ativo</p></div>
          </div>
        </div>
      </aside>

      <main className="min-w-0">
        <header className="flex h-20 items-center justify-between border-b border-border bg-card px-5 md:px-8">
          <div className="flex items-center gap-3">
            <Button variant="outline" size="icon" className="lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Abrir menu"><Menu /></Button>
            <div><p className="font-display text-lg font-bold text-primary">Centro de Controle</p><p className="hidden text-xs text-muted-foreground sm:block">Sistema Inteligente Adaptativo de Tráfego</p></div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`mr-2 hidden items-center gap-2 rounded-full px-3 py-1 text-xs font-bold sm:flex ${info.pill}`}><span className={`${info.pulso ? "live-pulse " : ""}size-2 rounded-full ${info.ponto}`} />{info.titulo}</div>
            <Button variant="ghost" size="icon" aria-label="Notificações"><Bell /></Button>
            <Button variant="outline" size="sm" onClick={() => void updateData()} disabled={refreshing}><RefreshCw className={refreshing ? "animate-spin" : ""} />Atualizar</Button>
          </div>
        </header>

        <div className="mx-auto max-w-[1500px] p-5 md:p-8">
          <section className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div><p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-signal-green">Operação em tempo real</p><h1 className="font-display text-3xl font-bold text-primary md:text-4xl">Visão geral do tráfego</h1><p className="mt-2 text-sm text-muted-foreground">Acompanhe o desempenho dos semáforos e o fluxo das vias monitoradas.</p></div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 size={15} />Atualizado às {updatedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}<ChevronDown size={14} /></div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores principais">
            <MetricCard icon={TrafficCone} label="Verde — Via 1" value={latest ? `${latest.tempo_via1}s` : "--"} detail="Tempo atual" accent="green" live={conectado} />
            <MetricCard icon={TrafficCone} label="Verde — Via 2" value={latest ? `${latest.tempo_via2}s` : "--"} detail="Tempo atual" accent="navy" live={conectado} />
            <MetricCard icon={CarFront} label="Veículos detectados" value={String(totalCars)} detail="Na janela monitorada" accent="yellow" live={serverOnline === true} />
            <MetricCard icon={conectado ? Wifi : WifiOff} label="Semáforos (ESP32)" value={valorConexao} detail={detalheConexao} accent={conectado ? "green" : conexao === "carregando" ? "navy" : "red"} live={conectado} />
          </section>

          <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_1fr]">
            <ChartPanel title="Tempos de verde por ciclo" subtitle="Duração do verde de cada via nos últimos ciclos" legend={[{ label: "Via 1", color: "bg-signal-green" }, { label: "Via 2", color: "bg-primary" }]} empty={chartTimes.length === 0}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartTimes} margin={{ top: 10, right: 6, left: -22, bottom: 0 }}>
                  <defs><linearGradient id="greenArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="var(--signal-green)" stopOpacity={0.22}/><stop offset="95%" stopColor="var(--signal-green)" stopOpacity={0}/></linearGradient></defs>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="hora" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis unit="s" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 6, fontSize: 12 }} />
                  <Area type="monotone" dataKey="tempo_via1" name="Via 1" stroke="var(--signal-green)" strokeWidth={3} fill="url(#greenArea)" />
                  <Area type="monotone" dataKey="tempo_via2" name="Via 2" stroke="var(--primary)" strokeWidth={3} fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartPanel>

            <ChartPanel title="Veículos detectados" subtitle="Volume por via nas últimas leituras" legend={[{ label: "Quantidade", color: "bg-primary" }]} empty={chartDetections.length === 0}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartDetections} margin={{ top: 10, right: 4, left: -25, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="hora" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 6, fontSize: 12 }} />
                  <Bar dataKey="quantidade_carros" name="Veículos" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartPanel>
          </section>

          <section className="mt-6 grid gap-6 xl:grid-cols-2">
            <ChartPanel title="Razão do fluxo por hora" subtitle="Participação de cada via no total de carros detectados (últimas 24 h)" legend={[{ label: "Via 1", color: "bg-signal-green" }, { label: "Via 2", color: "bg-primary" }]} empty={chartPorHora.length === 0}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartPorHora} margin={{ top: 10, right: 4, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="rotulo" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis unit="%" domain={[0, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ borderColor: "var(--border)", borderRadius: 6, fontSize: 12 }}
                    formatter={(value, name, item) => {
                      const carros = name === "Via 1" ? item.payload.carros_via1 : item.payload.carros_via2;
                      return [`${value}% (${carros} carros)`, name];
                    }}
                  />
                  <Bar dataKey="pct_via1" name="Via 1" stackId="razao" fill="var(--signal-green)" />
                  <Bar dataKey="pct_via2" name="Via 2" stackId="razao" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartPanel>

            <ChartPanel title="Tempo aberto por hora" subtitle="Soma do verde de cada via em cada hora (últimas 24 h)" legend={[{ label: "Via 1", color: "bg-signal-green" }, { label: "Via 2", color: "bg-primary" }]} empty={chartPorHora.length === 0}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartPorHora} margin={{ top: 10, right: 4, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="rotulo" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis unit=" min" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 6, fontSize: 12 }} formatter={(value, name) => [`${value} min`, name]} />
                  <Bar dataKey="min_via1" name="Via 1" fill="var(--signal-green)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="min_via2" name="Via 2" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartPanel>
          </section>

          <section className="mt-6 border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4"><div><h2 className="font-display text-base font-bold text-primary">Conexão dos semáforos</h2><p className="mt-1 text-xs text-muted-foreground">Comunicação do ESP32 com o servidor</p></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${info.pill}`}>{info.titulo}</span></div>
            <div className="grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0">
              <LinhaConexao ok={conectado} nome="ESP32 dos semáforos" detalhe={detalheEsp32} estado={estadoEsp32} />
              <LinhaConexao ok={serverOnline === true} nome="Servidor Flask" detalhe="O dashboard consulta o servidor a cada 5 segundos" estado={serverOnline === null ? "Verificando" : serverOnline ? "Respondendo" : "Sem resposta"} />
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail, accent, live = true }: { icon: typeof TrafficCone; label: string; value: string; detail: string; accent: "green" | "navy" | "yellow" | "red"; live?: boolean }) {
  const accents = { green: "bg-accent text-accent-foreground", navy: "bg-secondary text-secondary-foreground", yellow: "bg-signal-yellow/15 text-signal-yellow", red: "bg-signal-red/10 text-signal-red" };
  return <article className="border border-border bg-card p-5 shadow-[0_8px_30px_color-mix(in_oklab,var(--foreground)_5%,transparent)]"><div className="flex items-start justify-between"><div className={`flex size-10 items-center justify-center rounded-md ${accents[accent]}`}><Icon size={20} /></div>{live ? <span className="flex items-center gap-1 text-[11px] font-bold text-accent-foreground"><span className="size-1.5 rounded-full bg-signal-green" />AO VIVO</span> : <span className="flex items-center gap-1 text-[11px] font-bold text-signal-red"><span className="size-1.5 rounded-full bg-signal-red" />SEM SINAL</span>}</div><p className="mt-5 text-sm font-semibold text-muted-foreground">{label}</p><p className="mt-1 font-display text-3xl font-bold text-primary">{value}</p><p className="mt-2 text-xs text-muted-foreground">{detail}</p></article>;
}

function ChartPanel({ title, subtitle, legend, empty = false, children }: { title: string; subtitle: string; legend: { label: string; color: string }[]; empty?: boolean; children: React.ReactNode }) {
  return <article className="border border-border bg-card p-5 shadow-[0_8px_30px_color-mix(in_oklab,var(--foreground)_5%,transparent)] md:p-6"><div className="mb-6 flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-display text-base font-bold text-primary">{title}</h2><p className="mt-1 text-xs text-muted-foreground">{subtitle}</p></div><div className="flex gap-4">{legend.map((item) => <span key={item.label} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><span className={`size-2 rounded-full ${item.color}`} />{item.label}</span>)}</div></div><div className="h-[290px]">{empty ? <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Aguardando dados do sistema…</div> : children}</div></article>;
}

function LinhaConexao({ ok, nome, detalhe, estado }: { ok: boolean; nome: string; detalhe: string; estado: string }) {
  return <div className="flex items-center gap-3 p-5"><span className={`size-2.5 rounded-full ${ok ? "bg-signal-green" : "bg-signal-red"}`} /><div className="flex-1"><p className="text-sm font-bold text-foreground">{nome}</p><p className="mt-1 text-xs text-muted-foreground">{detalhe}</p></div><span className={`text-xs font-semibold ${ok ? "text-accent-foreground" : "text-signal-red"}`}>{estado}</span></div>;
}
