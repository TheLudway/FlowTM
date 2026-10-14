import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { LightbulbFilament, Question } from '@phosphor-icons/react';

interface MetricTooltipProps {
  title: string;
  description: string;
  interpretation?: string;
  flowtmGoal?: string;
}

export const MetricTooltip: React.FC<MetricTooltipProps> = ({
  title,
  description,
  interpretation,
  flowtmGoal,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState<{ top?: number; bottom?: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const timeoutRef = useRef<number | null>(null);

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const tooltipWidth = 290;

    // Horizontal calculation: center on trigger, clamp strictly inside viewport
    let left = rect.left + rect.width / 2 - tooltipWidth / 2;
    if (left + tooltipWidth > window.innerWidth - 16) {
      left = window.innerWidth - tooltipWidth - 16;
    }
    if (left < 16) {
      left = 16;
    }

    // Vertical calculation: show above if there is space (>190px above), otherwise below
    const showBelow = rect.top < 190;
    if (showBelow) {
      setCoords({
        top: rect.bottom + 8,
        left,
      });
    } else {
      setCoords({
        bottom: window.innerHeight - rect.top + 8,
        left,
      });
    }
  };

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    updatePosition();
    setIsVisible(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = window.setTimeout(() => {
      setIsVisible(false);
    }, 150);
  };

  // Close tooltip when user scrolls any container or resizes
  useEffect(() => {
    if (!isVisible) return;
    const handleScrollOrResize = () => setIsVisible(false);
    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [isVisible]);

  return (
    <div
      className="metric-tooltip-wrapper"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        ref={triggerRef}
        type="button"
        className="metric-tooltip-trigger"
        aria-label={`Información sobre ${title}`}
        onClick={(e) => {
          e.stopPropagation();
          updatePosition();
          setIsVisible((prev) => !prev);
        }}
      >
        <Question size={13} weight="bold" />
      </button>

      {isVisible && coords && typeof document !== 'undefined' &&
        createPortal(
          <div
            className="metric-tooltip-popover glass-panel"
            role="tooltip"
            style={{
              position: 'fixed',
              left: `${coords.left}px`,
              top: coords.top !== undefined ? `${coords.top}px` : undefined,
              bottom: coords.bottom !== undefined ? `${coords.bottom}px` : undefined,
              zIndex: 999999,
            }}
            onMouseEnter={() => {
              if (timeoutRef.current) clearTimeout(timeoutRef.current);
              setIsVisible(true);
            }}
            onMouseLeave={handleMouseLeave}
          >
            <div className="tooltip-header">
              <LightbulbFilament size={14} weight="fill" className="tooltip-icon" />
              <h6 className="tooltip-title">{title}</h6>
            </div>
            <p className="tooltip-desc">{description}</p>
            {interpretation && (
              <div className="tooltip-interpretation">
                <strong>¿Cómo interpretarlo?</strong> {interpretation}
              </div>
            )}
            {flowtmGoal && (
              <div className="tooltip-goal">
                <strong>Impacto FlowTM:</strong> {flowtmGoal}
              </div>
            )}
          </div>,
          document.body
        )}
    </div>
  );
};
