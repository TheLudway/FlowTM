import React from 'react';
import { ArrowCounterClockwise, FastForward, Pause, Play, Rewind } from '@phosphor-icons/react';

interface PlaybackBarProps {
  simTimeSec: number;
  durationSec: number;
  isPlaying: boolean;
  playbackSpeed: number;
  onTogglePlay: () => void;
  onReset: () => void;
  onSeek: (timeSec: number) => void;
  onSpeedChange: (speed: number) => void;
}

const SPEED_OPTIONS = [1, 2, 5, 10, 30, 60];

export const PlaybackBar: React.FC<PlaybackBarProps> = ({
  simTimeSec,
  durationSec,
  isPlaying,
  playbackSpeed,
  onTogglePlay,
  onReset,
  onSeek,
  onSpeedChange,
}) => {
  const progressPct = Math.min(100, Math.max(0, (simTimeSec / durationSec) * 100));

  const formatMinSec = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}m ${String(s).padStart(2, '0')}s`;
  };

  const handleSkip = (seconds: number) => {
    onSeek(Math.min(durationSec, Math.max(0, simTimeSec + seconds)));
  };

  return (
    <div className="playback-bar-container glass-panel">
      {/* Left controls: Play, Pause, Reset, Skips */}
      <div className="playback-controls-group">
        <button
          className="playback-btn reset-btn"
          onClick={onReset}
          title="Reiniciar Simulación al inicio (06:00:00 AM)"
          aria-label="Reiniciar"
        >
          <ArrowCounterClockwise size={18} weight="bold" />
        </button>

        <button
          className="playback-btn skip-btn"
          onClick={() => handleSkip(-60)}
          title="Retroceder 1 minuto"
        >
          <Rewind size={16} weight="bold" />
          <span>-1m</span>
        </button>

        <button
          className={`playback-btn play-toggle-btn ${isPlaying ? 'playing' : ''}`}
          onClick={onTogglePlay}
          title={isPlaying ? "Pausar (Barra espaciadora)" : "Reproducir (Barra espaciadora)"}
          aria-label={isPlaying ? "Pausar" : "Reproducir"}
        >
          {isPlaying ? (
            <Pause size={20} weight="fill" />
          ) : (
            <Play size={20} weight="fill" />
          )}
        </button>

        <button
          className="playback-btn skip-btn"
          onClick={() => handleSkip(60)}
          title="Avanzar 1 minuto"
        >
          <span>+1m</span>
          <FastForward size={16} weight="bold" />
        </button>
      </div>

      {/* Center: Timeline Progress Slider */}
      <div className="playback-timeline-section">
        <div className="timeline-time-info">
          <span className="tabular-nums font-mono time-current">
            {formatMinSec(simTimeSec)}
          </span>
          <span className="timeline-label">PROGRESO DE HORA PICO</span>
          <span className="tabular-nums font-mono time-total">
            {formatMinSec(durationSec)}
          </span>
        </div>

        <div className="timeline-slider-track">
          <input
            type="range"
            min={0}
            max={durationSec}
            step={1}
            value={simTimeSec}
            onChange={(e) => onSeek(parseFloat(e.target.value))}
            className="timeline-slider"
            style={{
              background: `linear-gradient(to right, var(--accent-red) 0%, var(--accent-yellow) ${progressPct}%, var(--border-default) ${progressPct}%, var(--border-default) 100%)`
            }}
          />
        </div>
      </div>

      {/* Right: Speed pills selector */}
      <div className="playback-speed-group">
        <span className="speed-group-label">VELOCIDAD:</span>
        <div className="speed-pills">
          {SPEED_OPTIONS.map((spd) => (
            <button
              key={spd}
              className={`speed-pill ${playbackSpeed === spd ? 'active' : ''}`}
              onClick={() => onSpeedChange(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
