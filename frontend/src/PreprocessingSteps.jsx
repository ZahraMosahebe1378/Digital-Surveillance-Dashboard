export default function PreprocessingSteps({ steps }) {
  if (!steps?.length) return null;

  return (
    <div className="steps-card">
      <ol className="steps-list">
        {steps.map((item) => (
          <li key={item.step} className="steps-item">
            <div className="steps-marker" aria-hidden="true">
              {item.step}
            </div>
            <div className="steps-body">
              <h3 className="steps-title">{item.title}</h3>
              <p className="steps-detail">{item.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
