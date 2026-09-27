import { Component } from "react";

// A render error anywhere in the tree would otherwise white-screen the whole
// app. This is the one class component in the codebase because React has no
// hook equivalent for catching render errors.
export default class ErrorBoundary extends Component {
  state = { crashed: false };

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  render() {
    if (this.state.crashed) {
      return (
        <div className="page page-narrow">
          <h1>Something went wrong</h1>
          <p className="muted">
            Reloading the page usually fixes this. If it keeps happening, tell
            your teacher.
          </p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}
