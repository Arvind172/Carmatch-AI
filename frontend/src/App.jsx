import { useEffect, useState } from 'react';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const COUNTRY_CODE = 'IN';

function formatPrice(price) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(price));
}

function VehicleCard({ car, saved, selected, onSave, onSelect, onDetails }) {
  const isSaved = saved.some((item) => item.id === car.id);

  return (
    <article className="vehicle-card">
      <div className={`vehicle-image image-${(car.id % 5) + 1}`}>
        <span className="image-tag">{car.vehicle.body_style}</span>
        <button
          className={`save-button ${isSaved ? 'is-saved' : ''}`}
          onClick={() => onSave(car)}
          aria-label={isSaved ? 'Remove saved car' : 'Save car'}
        >
          {isSaved ? '♥' : '♡'}
        </button>
        <div className="mini-car"><span /><i /><b /></div>
        <span className="image-caption">{car.vehicle.make.toUpperCase()}</span>
      </div>

      <div className="vehicle-content">
        <div className="card-overline">
          {car.vehicle.model_year} · {car.condition}
          {car.is_sample && <span className="sample-badge">SAMPLE</span>}
        </div>
        <h3>{car.vehicle.make} {car.vehicle.model}</h3>
        <p className="variant-name">
          {car.variant.name} · {car.variant.fuel_type} · {car.variant.transmission}
        </p>
        <div className="spec-row">
          <span><b>{car.variant.mileage_rating || '—'}</b> {car.variant.mileage_rating_unit}</span>
          <span><b>{car.variant.seating_capacity || '—'}</b> seats</span>
          <span>{car.city || car.country_code}</span>
        </div>
        {car.match_reasons?.length > 0 && (
          <div className="match-reasons">
            {car.match_reasons.map((reason) => <span key={reason}>✓ {reason}</span>)}
          </div>
        )}
        <div className="card-bottom">
          <strong>{formatPrice(car.price)}</strong>
          <div className="card-actions">
            <button
              className={`compare-checkbox ${selected ? 'selected' : ''}`}
              onClick={() => onSelect(car.id)}
            >
              {selected ? '✓ Selected' : 'Compare'}
            </button>
            <button className="details-link" onClick={() => onDetails(car)}>
              Details →
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

function App() {
  const [cars, setCars] = useState([]);
  const [savedCars, setSavedCars] = useState([]);
  const [comparisonCars, setComparisonCars] = useState([]);
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [filters, setFilters] = useState({
    body_style: '', fuel_type: '', condition: '', transmission: '', min_price: '', max_price: '',
  });
  const [selectedIds, setSelectedIds] = useState([]);
  const [view, setView] = useState('discover');
  const [detailCar, setDetailCar] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Could not load cars. Please try again.');
    }
    return response.status === 204 ? null : response.json();
  }

  async function loadCars() {
    setMessage('');
    try {
      const params = new URLSearchParams({ country_code: COUNTRY_CODE });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const result = await apiRequest(`/vehicles?${params}`);
      setCars(result.items);
      setComparisonCars([]);
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function loadSavedCars() {
    try {
      setSavedCars(await apiRequest('/saved'));
    } catch (error) {
      setMessage(error.message);
    }
  }

  useEffect(() => {
    loadCars();
  }, [filters]);

  useEffect(() => {
    loadSavedCars();
  }, []);

  async function findCars(event) {
    event.preventDefault();
    if (!query.trim()) {
      loadCars();
      return;
    }

    const message = query.trim();
    setLoading(true);
    setMessage('');
    try {
      const result = await apiRequest('/assistant', {
        method: 'POST',
        body: JSON.stringify({ message, country_code: COUNTRY_CODE, history: history.slice(-8) }),
      });
      setCars(result.items);
      setHistory([...history, { role: 'user', content: message }, { role: 'assistant', content: result.answer }].slice(-8));
      setQuery('');
      setView('discover');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleSavedCar(car) {
    const isSaved = savedCars.some((item) => item.id === car.id);
    try {
      if (isSaved) {
        await apiRequest(`/saved/${car.id}`, { method: 'DELETE' });
        setSavedCars(savedCars.filter((item) => item.id !== car.id));
      } else {
        await apiRequest(`/saved/${car.id}`, { method: 'POST' });
        setSavedCars([...savedCars, car]);
      }
    } catch (error) {
      setMessage(error.message);
    }
  }

  function toggleSelected(id) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      return current.length < 4 ? [...current, id] : current;
    });
  }

  async function compareCars() {
    try {
      setComparisonCars(await apiRequest('/compare', {
        method: 'POST',
        body: JSON.stringify({ listing_ids: selectedIds }),
      }));
      setSelectedIds([]);
    } catch (error) {
      setMessage(error.message);
    }
  }

  const shownCars = view === 'saved' ? savedCars : cars;
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home" onClick={() => setView('discover')}>
          <span className="brand-mark">C</span>
          <span>car<span className="brand-accent">match</span><small>CAR DISCOVERY</small></span>
        </a>
        <nav className="main-nav">
          <button onClick={() => { setView('discover'); loadCars(); }}>Discover</button>
          <button onClick={() => setView('saved')}>Saved ({savedCars.length})</button>
        </nav>
      </header>

      <main id="home">
        {view === 'discover' && (
          <section className="hero">
            <p className="eyebrow">A BETTER WAY TO FIND YOUR NEXT CAR</p>
            <h1>Find the car that <em>fits your life.</em></h1>
            <p className="hero-description">Describe what you need and see matching cars from our sample catalog.</p>
            <form className="search-box" onSubmit={findCars}>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Automatic SUV under ₹20 lakh for a family of five"
              />
              <button disabled={loading}>{loading ? 'Searching…' : 'Find cars'}</button>
            </form>
            {history.length > 0 && (
              <div className="assistant-history">
                {history.slice(-4).map((turn, index) => (
                  <p className={turn.role} key={`${index}-${turn.role}`}>{turn.content}</p>
                ))}
                <button onClick={() => setHistory([])}>Clear conversation</button>
              </div>
            )}
          </section>
        )}

        <section className="results-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{view === 'saved' ? 'YOUR SHORTLIST' : 'SAMPLE VEHICLES'}</p>
              <h2>{view === 'saved' ? 'Saved cars' : view === 'compare' ? 'Compare cars' : 'Explore cars'}</h2>
            </div>
            <span className="sample-note">SAMPLE LISTINGS · NOT LIVE OFFERS</span>
          </div>

          {comparisonCars.length > 0 && view !== 'saved' && (
            <section className="comparison-panel">
              <div className="comparison-heading">
                <h3>Side-by-side comparison</h3>
                <button onClick={() => setComparisonCars([])}>Close comparison</button>
              </div>
              <div className="comparison-table-wrap">
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th>Feature</th>
                      {comparisonCars.map((car) => (
                        <th key={car.id}>{car.vehicle.model_year} {car.vehicle.make} {car.vehicle.model}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Price', (car) => formatPrice(car.price)],
                      ['Condition', (car) => car.condition],
                      ['Body style', (car) => car.vehicle.body_style || '—'],
                      ['Fuel', (car) => car.variant.fuel_type || '—'],
                      ['Transmission', (car) => car.variant.transmission || '—'],
                      ['Efficiency', (car) => `${car.variant.mileage_rating || '—'} ${car.variant.mileage_rating_unit || ''}`],
                      ['Seats', (car) => car.variant.seating_capacity || '—'],
                      ['Location', (car) => car.city || '—'],
                    ].map(([feature, value]) => (
                      <tr key={feature}>
                        <th>{feature}</th>
                        {comparisonCars.map((car) => <td key={car.id}>{value(car)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <div className="filter-row">
            <select value={filters.body_style} onChange={(event) => setFilters({ ...filters, body_style: event.target.value })}>
              <option value="">All body styles</option>
              {['SUV', 'Sedan', 'Hatchback', 'Pickup', 'Wagon'].map((body) => <option key={body}>{body}</option>)}
            </select>
            <select value={filters.fuel_type} onChange={(event) => setFilters({ ...filters, fuel_type: event.target.value })}>
              <option value="">All fuel types</option>
              {['Petrol', 'Gasoline', 'Diesel', 'Hybrid', 'Electric'].map((fuel) => <option key={fuel}>{fuel}</option>)}
            </select>
            <select value={filters.condition} onChange={(event) => setFilters({ ...filters, condition: event.target.value })}>
              <option value="">New and used</option>
              <option>New</option><option>Used</option>
            </select>
            <select value={filters.transmission} onChange={(event) => setFilters({ ...filters, transmission: event.target.value })}>
              <option value="">Any transmission</option>
              <option>Automatic</option><option>Manual</option>
            </select>
            <input aria-label="Minimum price" type="number" placeholder="Min ₹" value={filters.min_price} onChange={(event) => setFilters({ ...filters, min_price: event.target.value })} />
            <input aria-label="Maximum price" type="number" placeholder="Max ₹" value={filters.max_price} onChange={(event) => setFilters({ ...filters, max_price: event.target.value })} />
            <select aria-label="Sort by price" onChange={(event) => setFilters({ ...filters, sort: event.target.value })}>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </select>
          </div>

          {message && <p className="error-message">{message}</p>}
          {loading && <p className="status-message">Finding matching cars…</p>}

          {!loading && shownCars.length > 0 && (
            <div className="vehicle-grid">
              {shownCars.map((car) => (
                <VehicleCard
                  key={car.id}
                  car={car}
                  saved={savedCars}
                  selected={selectedIds.includes(car.id)}
                  onSave={toggleSavedCar}
                  onSelect={toggleSelected}
                  onDetails={setDetailCar}
                />
              ))}
            </div>
          )}
          {!loading && shownCars.length === 0 && (
            <div className="empty-state">
              <h3>{view === 'saved' ? 'No saved cars yet' : 'No cars match those filters'}</h3>
              <p>{view === 'saved' ? 'Save a car with the heart button to find it here.' : 'Try changing your search or filters.'}</p>
            </div>
          )}
        </section>
      </main>

      <footer>
        <span>carmatch</span>
        <span>Vehicle data and prices are illustrative samples, not live offers.</span>
      </footer>

      {selectedIds.length > 0 && view !== 'saved' && (
        <div className="compare-tray">
          <span>{selectedIds.length} car{selectedIds.length === 1 ? '' : 's'} selected</span>
          <button className="clear-selection" onClick={() => setSelectedIds([])}>Clear</button>
          <button className="compare-button" disabled={selectedIds.length < 2} onClick={compareCars}>
            {selectedIds.length < 2 ? 'Select one more car' : 'Compare now'}
          </button>
        </div>
      )}

      {detailCar && (
        <div className="modal-backdrop" onClick={() => setDetailCar(null)}>
          <section className="detail-modal" onClick={(event) => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setDetailCar(null)}>×</button>
            <p className="eyebrow">{detailCar.vehicle.model_year} · {detailCar.condition}</p>
            <h2>{detailCar.vehicle.make} {detailCar.vehicle.model}</h2>
            <p>{detailCar.vehicle.description}</p>
            <strong className="detail-price">{formatPrice(detailCar.price)} <small>sample price</small></strong>
            <dl className="detail-specs">
              <div><dt>Body</dt><dd>{detailCar.vehicle.body_style}</dd></div>
              <div><dt>Fuel</dt><dd>{detailCar.variant.fuel_type}</dd></div>
              <div><dt>Transmission</dt><dd>{detailCar.variant.transmission}</dd></div>
              <div><dt>Drive</dt><dd>{detailCar.variant.drivetrain}</dd></div>
              <div><dt>Efficiency</dt><dd>{detailCar.variant.mileage_rating} {detailCar.variant.mileage_rating_unit}</dd></div>
              <div><dt>Seats</dt><dd>{detailCar.variant.seating_capacity}</dd></div>
              <div><dt>Location</dt><dd>{detailCar.city}</dd></div>
              <div><dt>Mileage</dt><dd>{detailCar.odometer_value ? `${detailCar.odometer_value} ${detailCar.odometer_unit}` : 'New'}</dd></div>
            </dl>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
