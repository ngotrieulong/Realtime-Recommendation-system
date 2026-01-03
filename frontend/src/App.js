/**
 * ==========================================================================
 * MOVIE RECOMMENDATION SYSTEM - REACT FRONTEND
 * ==========================================================================
 * Main application component with routing and global state
 */

import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import './App.css';
import { MOCK_MOVIES, MOCK_METRICS } from './mockData';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// =============================================================================
// API SERVICE - Communication with Backend
// =============================================================================


// Toggle between Mock and Real API
const USE_MOCK_API = true;

// =============================================================================
// API SERVICE - Communication with Backend (or Mock)
// =============================================================================
class RecommendationAPI {

    /**
     * Get personalized recommendations for a user
     */
    static async getRecommendations(userId, sessionId = null) {
        if (USE_MOCK_API) {
            // Simulate network delay
            await new Promise(resolve => setTimeout(resolve, 800));
            return {
                user_id: userId,
                recommendations: MOCK_MOVIES,
                metadata: {
                    source: 'hybrid',
                    cached: false,
                    computation_time_ms: 45,
                    rec_log_id: 12345,
                    model_version: 'mock_v1'
                }
            };
        }

        const params = new URLSearchParams({ user_id: userId });
        if (sessionId) params.append('session_id', sessionId);

        const response = await fetch(`${API_BASE_URL}/api/recommendations?${params}`);

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Track user interaction event
     */
    static async trackEvent(eventData) {
        if (USE_MOCK_API) {
            console.log("📝 [MOCK] Event Tracked:", eventData);
            return { status: "accepted", message: "Mock event tracked" };
        }

        const response = await fetch(`${API_BASE_URL}/api/events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(eventData),
        });

        if (!response.ok) {
            throw new Error(`Event tracking failed: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Get all movies (browse catalog)
     */
    static async getMovies(limit = 50) {
        if (USE_MOCK_API) {
            await new Promise(resolve => setTimeout(resolve, 500));
            return {
                movies: MOCK_MOVIES,
                count: MOCK_MOVIES.length,
                limit: limit,
                offset: 0
            }
        }

        const response = await fetch(`${API_BASE_URL}/api/movies?limit=${limit}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch movies: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Get system metrics
     */
    static async getMetrics() {
        if (USE_MOCK_API) {
            await new Promise(resolve => setTimeout(resolve, 300));
            return MOCK_METRICS;
        }

        const response = await fetch(`${API_BASE_URL}/api/metrics`);

        if (!response.ok) {
            throw new Error(`Failed to fetch metrics: ${response.status}`);
        }

        return await response.json();
    }
}

// =============================================================================
// MOVIE CARD COMPONENT
// =============================================================================
function MovieCard({ movie, onInteraction, isRecommended = false, position = null, recLogId = null }) {
    const [isClicked, setIsClicked] = useState(false);
    const [userRating, setUserRating] = useState(null);

    const handleClick = async () => {
        setIsClicked(true);

        await onInteraction({
            movie_id: movie.movie_id,
            event_type: 'click',
            rec_log_id: recLogId,
        });
    };

    const handleRate = async (rating) => {
        setUserRating(rating);

        await onInteraction({
            movie_id: movie.movie_id,
            event_type: 'rate',
            rating: rating,
            rec_log_id: recLogId,
        });
    };

    return (
        <div className={`movie-card ${isClicked ? 'clicked' : ''}`} onClick={handleClick}>
            {/* Movie Poster */}
            <div className="movie-poster">
                <img
                    src={movie.poster_url || `https://via.placeholder.com/300x450?text=${movie.title}`}
                    alt={movie.title}
                    onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = `https://via.placeholder.com/300x450?text=${movie.title}`;
                    }}
                />

                {/* Recommendation Badge */}
                {isRecommended && (
                    <div className="rec-badge">
                        ✨ Recommended {position && `#${position}`}
                    </div>
                )}

                {/* Score Badge */}
                {movie.score && (
                    <div className="score-badge">
                        {(movie.score * 100).toFixed(0)}% Match
                    </div>
                )}
            </div>

            {/* Movie Info */}
            <div className="movie-info">
                <h3 className="movie-title">{movie.title}</h3>

                {/* Rating */}
                <div className="rating-container">
                    {[1, 2, 3, 4, 5].map(star => (
                        <span
                            key={star}
                            className={`star ${userRating >= star ? 'filled' : ''}`}
                            onClick={(e) => {
                                e.stopPropagation();
                                handleRate(star);
                            }}
                        >
                            ★
                        </span>
                    ))}
                </div>

                {/* Metadata */}
                {movie.release_year && (
                    <p className="movie-year">{movie.release_year}</p>
                )}

                {/* Source indicator (for debugging) */}
                {movie.source && (
                    <span className="source-tag">{movie.source}</span>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// RECOMMENDATION PANEL COMPONENT
// =============================================================================
function RecommendationPanel({ userId, sessionId }) {
    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [metadata, setMetadata] = useState(null);

    // Fetch recommendations on mount
    useEffect(() => {
        fetchRecommendations();
    }, [userId]);

    const fetchRecommendations = async () => {
        try {
            setLoading(true);
            setError(null);

            const data = await RecommendationAPI.getRecommendations(userId, sessionId);

            setRecommendations(data.recommendations);
            setMetadata(data.metadata);

        } catch (err) {
            setError(err.message);
            console.error('Failed to fetch recommendations:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleInteraction = async (eventData) => {
        try {
            await RecommendationAPI.trackEvent({
                user_id: userId,
                session_id: sessionId,
                ...eventData,
            });

            console.log('✅ Event tracked:', eventData);
        } catch (err) {
            console.error('❌ Event tracking failed:', err);
        }
    };

    if (loading) {
        return (
            <div className="recommendation-panel loading">
                <div className="spinner"></div>
                <p>Loading your personalized recommendations...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="recommendation-panel error">
                <p>❌ Error: {error}</p>
                <button onClick={fetchRecommendations}>Retry</button>
            </div>
        );
    }

    return (
        <div className="recommendation-panel">
            {/* Header */}
            <div className="panel-header">
                <h2>🎬 Recommended For You</h2>

                {/* Metadata */}
                {metadata && (
                    <div className="metadata-info">
                        <span className="badge">
                            {metadata.source === 'hybrid' ? '🔀 Hybrid' :
                                metadata.source === 'realtime' ? '⚡ Real-time' :
                                    metadata.source === 'batch' ? '📊 Batch' :
                                        '🔥 Popular'}
                        </span>
                        <span className="badge">
                            {metadata.cached ? '💾 Cached' : '🆕 Fresh'}
                        </span>
                        <span className="latency">
                            {metadata.computation_time_ms}ms
                        </span>
                    </div>
                )}

                <button className="refresh-btn" onClick={fetchRecommendations}>
                    🔄 Refresh
                </button>
            </div>

            {/* Movie Grid */}
            <div className="movie-grid">
                {recommendations.map((movie, index) => (
                    <MovieCard
                        key={movie.movie_id}
                        movie={movie}
                        onInteraction={handleInteraction}
                        isRecommended={true}
                        position={index + 1}
                        recLogId={metadata?.rec_log_id}
                    />
                ))}
            </div>

            {/* Debug Info */}
            {metadata && (
                <details className="debug-info">
                    <summary>🔍 Debug Info</summary>
                    <pre>{JSON.stringify(metadata, null, 2)}</pre>
                </details>
            )}
        </div>
    );
}

// =============================================================================
// ANALYTICS DASHBOARD COMPONENT
// =============================================================================
function AnalyticsDashboard() {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchMetrics();

        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchMetrics, 30000);
        return () => clearInterval(interval);
    }, []);

    const fetchMetrics = async () => {
        try {
            const data = await RecommendationAPI.getMetrics();
            setMetrics(data);
            setLoading(false);
        } catch (err) {
            console.error('Failed to fetch metrics:', err);
        }
    };

    if (loading || !metrics) {
        return <div className="analytics-dashboard loading">Loading metrics...</div>;
    }

    return (
        <div className="analytics-dashboard">
            <h2>📊 System Metrics</h2>

            <div className="metrics-grid">
                {/* Cache Metrics */}
                <div className="metric-card">
                    <h3>Cache Performance</h3>
                    <div className="metric-value">{metrics.cache.hit_rate_percent}%</div>
                    <div className="metric-label">Hit Rate</div>
                    <div className="metric-detail">
                        {metrics.cache.cache_hits} / {metrics.cache.total_requests} requests
                    </div>
                </div>

                {/* Recommendation Metrics */}
                <div className="metric-card">
                    <h3>Recommendations</h3>
                    <div className="metric-value">{metrics.recommendations.total_served}</div>
                    <div className="metric-label">Served (Last Hour)</div>
                </div>

                {/* CTR Metrics */}
                <div className="metric-card">
                    <h3>Click-Through Rate</h3>
                    <div className="metric-value">{metrics.recommendations.ctr_percent}%</div>
                    <div className="metric-label">CTR</div>
                    <div className="metric-detail">
                        {metrics.recommendations.total_clicks} clicks
                    </div>
                </div>
            </div>

            <div className="last-updated">
                Last updated: {new Date(metrics.timestamp).toLocaleTimeString()}
            </div>
        </div>
    );
}

// =============================================================================
// MAIN APP COMPONENT
// =============================================================================
function App() {
    // Session management
    const [userId] = useState(() => {
        // Get from localStorage or create new
        let userId = localStorage.getItem('userId');
        if (!userId) {
            userId = `user_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem('userId', userId);
        }
        return userId;
    });

    const [sessionId] = useState(() => {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    });

    return (
        <Router>
            <div className="App">
                {/* Header */}
                <header className="app-header">
                    <div className="header-content">
                        <h1>🎬 MovieRec AI</h1>
                        <nav className="app-nav">
                            <Link to="/" className="nav-link">🎬 Recommendations</Link>
                            <Link to="/analytics" className="nav-link">📊 Analytics</Link>
                        </nav>
                    </div>
                </header>

                {/* Main Content */}
                <main className="app-main">
                    <Routes>
                        <Route path="/" element={<RecommendationPanel userId={userId} sessionId={sessionId} />} />
                        <Route path="/analytics" element={<AnalyticsDashboard />} />
                    </Routes>
                </main>

                {/* Footer */}
                <footer className="app-footer">
                    <p>Powered by Lambda Architecture (Batch + Real-time)</p>
                </footer>
            </div>
        </Router>
    );
}

export default App;
