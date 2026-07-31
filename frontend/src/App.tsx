const foundationItems = [
  {
    label: "Backend",
    value: "FastAPI",
    description: "상태 확인과 향후 REST API를 위한 기반",
  },
  {
    label: "Frontend",
    value: "React + TypeScript",
    description: "주간 온보딩 경험을 위한 웹 애플리케이션 기반",
  },
  {
    label: "Deployment",
    value: "Single origin",
    description: "Vite 빌드를 FastAPI가 함께 제공하는 구조",
  },
];

export default function App() {
  return (
    <main className="app-shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">INTERX ONBOARDING · PROJECT SCAFFOLD</p>
        <div className="hero-copy">
          <h1 id="page-title">IX Value Loop</h1>
          <p>
            실제 업무 속 행동을 핵심가치와 연결하고, 근거와 피드백으로 축적하는 온보딩
            포털의 개발 기반입니다.
          </p>
        </div>
        <span className="status-badge">Foundation ready</span>
      </section>

      <section className="foundation-grid" aria-label="Scaffold components">
        {foundationItems.map((item) => (
          <article className="foundation-card" key={item.label}>
            <span>{item.label}</span>
            <h2>{item.value}</h2>
            <p>{item.description}</p>
          </article>
        ))}
      </section>

      <footer>
        <p>다음 단계: PostgreSQL 데이터 모델과 Alembic migration</p>
      </footer>
    </main>
  );
}
