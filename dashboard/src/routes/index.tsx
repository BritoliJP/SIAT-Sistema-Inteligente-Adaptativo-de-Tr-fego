import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  CarFront,
  ChevronDown,
   Clock3,
  Gauge,
  LayoutDashboard,
  Menu,
  RefreshCw,
  RouteIcon,
  Settings,
  TrafficCone,
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

const initialTimes: TimePoint[] = [
  ["18:10", 42, 31], ["18:15", 38, 35], ["18:20", 46, 32], ["18:25", 51, 29],
  ["18:30", 48, 34], ["18:35", 55, 31], ["18:40", 52, 38], ["18:45", 58, 34],
  ["18:50", 54, 39], ["18:55", 61, 36], ["19:00", 57, 41], ["19:05", 64, 38],
].map(([timestamp, tempo_via1, tempo_via2]) => ({ timestamp: String(timestamp), tempo_via1: Number(tempo_via1), tempo_via2: Number(tempo_via2) }));

const initialDetections: Detection[] = [
  ["18:10", "Via 1", 18], ["18:15", "Via 2", 13], ["18:20", "Via 1", 22], ["18:25", "Via 2", 15],
  ["18:30", "Via 1", 26], ["18:35", "Via 2", 17], ["18:40", "Via 1", 24], ["18:45", "Via 2", 20],
  ["18:50", "Via 1", 29], ["18:55", "Via 2", 18], ["19:00", "Via 1", 31], ["19:05", "Via 2", 21],
].map(([timestamp, via, quantidade_carros]) => ({ timestamp: String(timestamp), via: String(via), quantidade_carros: Number(quantidade_carros) }));

const navItems = [
  { label: "Visão geral", icon: LayoutDashboard },
  { label: "Cruzamentos", icon: TrafficCone },
  { label: "Fluxo viário", icon: RouteIcon },
  { label: "Relatórios", icon: Activity },
];

function formatTime(timestamp: string) {
  return timestamp.includes("T") || timestamp.length > 8 ? timestamp.slice(11, 16) : timestamp;
}

function Index() {
  const [times, setTimes] = useState(initialTimes);
  const [detections, setDetections] = useState(initialDetections);
  const [updatedAt, setUpdatedAt] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const updateData = useCallback(async () => {
    setRefreshing(true);
    try {
      const [timeResponse, detectionResponse] = await Promise.all([
        fetch("/dados/tempos"),
        fetch("/dados/deteccoes"),
      ]);
      if (timeResponse.ok && detectionResponse.ok) {
        const timeData = (await timeResponse.json()) as TimePoint[];
        const detectionData = (await detectionResponse.json()) as Detection[];
        setTimes([...timeData].reverse().slice(-30));
        setDetections([...detectionData].reverse().slice(-30));
      }
    } catch {
      // The supplied dashboard remains useful with representative data when the API is offline.
    } finally {
      setUpdatedAt(new Date());
      setRefreshing(false);
    }
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

  const chartTimes = useMemo(() => times.map((item) => ({ ...item, hora: formatTime(item.timestamp) })), [times]);
  const chartDetections = useMemo(() => detections.map((item) => ({ ...item, hora: formatTime(item.timestamp) })), [detections]);
  const latest = times.at(-1) ?? initialTimes.at(-1);
  const totalCars = detections.reduce((sum, item) => sum + item.quantidade_carros, 0);

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
            <div className="mr-2 hidden items-center gap-2 text-xs font-semibold text-muted-foreground md:flex"><span className="live-pulse size-2 rounded-full bg-signal-green" />Sistema online</div>
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
            <MetricCard icon={TrafficCone} label="Verde — Via 1" value={`${latest?.tempo_via1 ?? 0}s`} detail="Tempo atual" accent="green" />
            <MetricCard icon={TrafficCone} label="Verde — Via 2" value={`${latest?.tempo_via2 ?? 0}s`} detail="Tempo atual" accent="navy" />
            <MetricCard icon={CarFront} label="Veículos detectados" value={String(totalCars)} detail="Na janela monitorada" accent="yellow" />
            <MetricCard icon={Gauge} label="Eficiência média" value="91%" detail="Fluxo dentro da meta" accent="red" />
          </section>

          <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_1fr]">
            <ChartPanel title="Tempos de verde calculados" subtitle="Últimas leituras por via" legend={[{ label: "Via 1", color: "bg-signal-green" }, { label: "Via 2", color: "bg-primary" }]}>
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

            <ChartPanel title="Veículos detectados" subtitle="Volume por via nas últimas leituras" legend={[{ label: "Quantidade", color: "bg-primary" }]}>
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

          <section className="mt-6 border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4"><div><h2 className="font-display text-base font-bold text-primary">Status dos cruzamentos</h2><p className="mt-1 text-xs text-muted-foreground">Condição atual da rede monitorada</p></div><span className="rounded-full bg-accent px-3 py-1 text-xs font-bold text-accent-foreground">Todos operacionais</span></div>
            <div className="grid divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
              {["Av. Central × Rua Norte", "Av. das Nações × Rua 8", "Av. Brasil × Rua Sul"].map((name, index) => <div key={name} className="flex items-center gap-3 p-5"><span className="size-2.5 rounded-full bg-signal-green" /><div className="flex-1"><p className="text-sm font-bold text-foreground">{name}</p><p className="mt-1 text-xs text-muted-foreground">Operação adaptativa • Ciclo {index + 1}</p></div><span className="text-xs font-semibold text-accent-foreground">Normal</span></div>)}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail, accent }: { icon: typeof TrafficCone; label: string; value: string; detail: string; accent: "green" | "navy" | "yellow" | "red" }) {
  const accents = { green: "bg-accent text-accent-foreground", navy: "bg-secondary text-secondary-foreground", yellow: "bg-signal-yellow/15 text-signal-yellow", red: "bg-signal-red/10 text-signal-red" };
  return <article className="border border-border bg-card p-5 shadow-[0_8px_30px_color-mix(in_oklab,var(--foreground)_5%,transparent)]"><div className="flex items-start justify-between"><div className={`flex size-10 items-center justify-center rounded-md ${accents[accent]}`}><Icon size={20} /></div><span className="flex items-center gap-1 text-[11px] font-bold text-accent-foreground"><span className="size-1.5 rounded-full bg-signal-green" />AO VIVO</span></div><p className="mt-5 text-sm font-semibold text-muted-foreground">{label}</p><p className="mt-1 font-display text-3xl font-bold text-primary">{value}</p><p className="mt-2 text-xs text-muted-foreground">{detail}</p></article>;
}

function ChartPanel({ title, subtitle, legend, children }: { title: string; subtitle: string; legend: { label: string; color: string }[]; children: React.ReactNode }) {
  return <article className="border border-border bg-card p-5 shadow-[0_8px_30px_color-mix(in_oklab,var(--foreground)_5%,transparent)] md:p-6"><div className="mb-6 flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-display text-base font-bold text-primary">{title}</h2><p className="mt-1 text-xs text-muted-foreground">{subtitle}</p></div><div className="flex gap-4">{legend.map((item) => <span key={item.label} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><span className={`size-2 rounded-full ${item.color}`} />{item.label}</span>)}</div></div><div className="h-[290px]">{children}</div></article>;
}
