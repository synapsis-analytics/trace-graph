import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Explore from "./pages/Explore";
import PathFinder from "./pages/PathFinder";
import Framework from "./pages/Framework";
import Coverage from "./pages/Coverage";
import Registry from "./pages/Registry";
import Ask from "./pages/Ask";
import ApiGuide from "./pages/ApiGuide";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Explore />} />
        <Route path="/path" element={<PathFinder />} />
        <Route path="/framework" element={<Framework />} />
        <Route path="/coverage" element={<Coverage />} />
        <Route path="/registry" element={<Registry />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/api-guide" element={<ApiGuide />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
