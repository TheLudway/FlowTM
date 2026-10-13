import React, { useEffect, useRef } from 'react';
import type { FeatureCollection } from 'geojson';
import * as maplibregl from 'maplibre-gl';
import type { InterpolatedBus, RouteConfig, SelectedEntity, Station, ThemeMode } from '../types';

// Set self-hosted Web Worker URL to prevent Vite 404 worker error
maplibregl.setWorkerUrl('/maplibre-gl-worker.mjs');

interface MapViewportProps {
  theme: ThemeMode;
  resolvedTheme: 'dark' | 'light';
  stations: Station[];
  routes: RouteConfig[];
  activeBuses: InterpolatedBus[];
  currentQueues: Record<string, number>;
  selectedEntity: SelectedEntity | null;
  onSelectEntity: (entity: SelectedEntity | null) => void;
  isCameraFollowing?: boolean;
  onStopCameraFollowing?: () => void;
}

export const MapViewport: React.FC<MapViewportProps> = ({
  resolvedTheme,
  stations,
  activeBuses,
  currentQueues,
  selectedEntity,
  onSelectEntity,
  isCameraFollowing = false,
  onStopCameraFollowing,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const isLoadedRef = useRef(false);

  // Latest refs to prevent stale closure in animation loops and callbacks
  const activeBusesRef = useRef<InterpolatedBus[]>(activeBuses);
  const stationsRef = useRef<Station[]>(stations);
  const currentQueuesRef = useRef<Record<string, number>>(currentQueues);

  useEffect(() => {
    activeBusesRef.current = activeBuses;
  }, [activeBuses]);

  useEffect(() => {
    stationsRef.current = stations;
  }, [stations]);

  useEffect(() => {
    currentQueuesRef.current = currentQueues;
  }, [currentQueues]);

  const isDark = resolvedTheme === 'dark';

  // Helper: push latest active buses to GeoJSON source
  const updateBusesSource = () => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;

    const source = map.getSource('active-buses') as maplibregl.GeoJSONSource | undefined;
    if (source) {
      const geojson: FeatureCollection = {
        type: 'FeatureCollection',
        features: activeBusesRef.current.map((b) => ({
          type: 'Feature',
          properties: {
            bus_id: b.bus_id,
            route: b.route,
            occupancy_pct: b.occupancy_pct,
            passengers: b.passengers,
            is_stopped: b.is_stopped ? 1 : 0,
            is_bunching: b.is_bunching ? 1 : 0,
            speed_kmh: b.speed_kmh || 0,
            bus_type: b.bus_type || 'articulado',
            capacity: b.capacity || 160,
            length_m: b.length_m || 18,
          },
          geometry: {
            type: 'Point',
            coordinates: [b.lon, b.lat],
          },
        })),
      };
      source.setData(geojson);
    }
  };

  // Helper: push latest stations & queue counts to GeoJSON source
  const updateStationsSource = () => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;

    const source = map.getSource('stations') as maplibregl.GeoJSONSource | undefined;
    if (source && stationsRef.current.length > 0) {
      const geojson: FeatureCollection = {
        type: 'FeatureCollection',
        features: stationsRef.current.map((s) => ({
          type: 'Feature',
          properties: {
            code: s.code,
            name: s.name,
            sequence: s.sequence,
            queue: currentQueuesRef.current[s.code] || 0,
          },
          geometry: {
            type: 'Point',
            coordinates: [s.lon, s.lat],
          },
        })),
      };
      source.setData(geojson);
    }
  };

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const baseStyle: maplibregl.StyleSpecification = {
      version: 8,
      glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
      sources: {
        'esri-dark': {
          type: 'raster',
          tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          maxzoom: 16,
          attribution: '© Esri Canvas, © OpenStreetMap',
        },
        'esri-light': {
          type: 'raster',
          tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          maxzoom: 16,
          attribution: '© Esri Canvas, © OpenStreetMap',
        },
      },
      layers: [
        {
          id: 'bg-layer',
          type: 'background',
          paint: {
            'background-color': isDark ? '#14171D' : '#F4F5F7',
          },
        },
        {
          id: 'esri-dark-tiles',
          type: 'raster',
          source: 'esri-dark',
          minzoom: 0,
          maxzoom: 22,
          layout: {
            visibility: isDark ? 'visible' : 'none',
          },
        },
        {
          id: 'esri-light-tiles',
          type: 'raster',
          source: 'esri-light',
          minzoom: 0,
          maxzoom: 22,
          layout: {
            visibility: isDark ? 'none' : 'visible',
          },
        },
      ],
    };

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: baseStyle,
      center: [-74.057, 4.693], // Corridor midpoint
      zoom: 12.8,
      pitch: 28,
      bearing: -12,
      maxZoom: 20,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-left');

    map.on('dragstart', () => {
      if (onStopCameraFollowing) onStopCameraFollowing();
    });

    map.on('error', (e: any) => {
      console.error('[MapLibre]', e?.error?.message || e?.message || e);
    });

    const initOperations = () => {
      if (isLoadedRef.current) return;
      isLoadedRef.current = true;
      setupOperationalLayers(map);
    };

    map.on('style.load', initOperations);
    map.on('load', initOperations);
    map.on('idle', initOperations);
    map.on('render', () => {
      if (map.isStyleLoaded()) {
        initOperations();
      }
    });

    if (map.isStyleLoaded()) {
      initOperations();
    }

    mapRef.current = map;

    return () => {
      isLoadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Instant Theme switching
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;

    if (map.getLayer('esri-dark-tiles')) {
      map.setLayoutProperty('esri-dark-tiles', 'visibility', isDark ? 'visible' : 'none');
    }
    if (map.getLayer('esri-light-tiles')) {
      map.setLayoutProperty('esri-light-tiles', 'visibility', isDark ? 'none' : 'visible');
    }
    if (map.getLayer('bg-layer')) {
      map.setPaintProperty('bg-layer', 'background-color', isDark ? '#14171D' : '#F4F5F7');
    }

    if (map.getLayer('tm-network-all')) {
      map.setPaintProperty(
        'tm-network-all',
        'line-color',
        isDark ? 'rgba(255, 255, 255, 0.22)' : 'rgba(0, 0, 0, 0.22)'
      );
    }
    if (map.getLayer('all-stations-dots')) {
      map.setPaintProperty(
        'all-stations-dots',
        'circle-color',
        isDark ? '#484F58' : '#9CA3AF'
      );
    }
    if (map.getLayer('station-labels')) {
      map.setPaintProperty('station-labels', 'text-color', isDark ? '#FFFFFF' : '#111827');
      map.setPaintProperty('station-labels', 'text-halo-color', isDark ? '#0E1117' : '#FFFFFF');
    }
    if (map.getLayer('station-dot')) {
      map.setPaintProperty('station-dot', 'circle-color', isDark ? '#161B22' : '#FFFFFF');
    }
    if (map.getLayer('bus-dot')) {
      map.setPaintProperty('bus-dot', 'circle-stroke-color', isDark ? '#FFFFFF' : '#1A202C');
    }
  }, [isDark]);

  // Setup Infrastructure, Stations, and Fleet in exact z-index order
  const setupOperationalLayers = async (map: maplibregl.Map) => {
    try {
      const [trazadosGeoJSON, allStationsGeoJSON, initialStations] = await Promise.all([
        fetch('/data/infra_troncal/trazados.geojson').then((res) => res.json()),
        fetch('/data/infra_troncal/estaciones.geojson').then((res) => res.json()),
        fetch('/data/stations.json').then((res) => res.json()),
      ]);

      // 1. Full TransMilenio Network (All 20 corridors)
      if (!map.getSource('tm-trazados')) {
        map.addSource('tm-trazados', {
          type: 'geojson',
          data: trazadosGeoJSON,
        });

        // Background network lines
        map.addLayer({
          id: 'tm-network-all',
          type: 'line',
          source: 'tm-trazados',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': isDark ? 'rgba(255, 255, 255, 0.22)' : 'rgba(0, 0, 0, 0.22)',
            'line-width': 2.5,
            'line-dasharray': [3, 2],
          },
        });

        // Active Pilot Corridor Glow (Caracas Centro & Autonorte)
        map.addLayer({
          id: 'active-corridor-glow',
          type: 'line',
          source: 'tm-trazados',
          filter: ['in', 'id_trazado', 'TZ002', 'TZ001'],
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#E53935',
            'line-width': 9,
            'line-opacity': 0.35,
            'line-blur': 3,
          },
        });

        // Active Corridor Primary Lane
        map.addLayer({
          id: 'active-corridor-line',
          type: 'line',
          source: 'tm-trazados',
          filter: ['in', 'id_trazado', 'TZ002', 'TZ001'],
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#E53935',
            'line-width': 4.5,
            'line-opacity': 0.95,
          },
        });
      }

      // 2. TransMilenio Reference Stations (150 network stations)
      if (!map.getSource('tm-all-stations')) {
        map.addSource('tm-all-stations', {
          type: 'geojson',
          data: allStationsGeoJSON,
        });

        map.addLayer({
          id: 'all-stations-dots',
          type: 'circle',
          source: 'tm-all-stations',
          paint: {
            'circle-radius': 3.5,
            'circle-color': isDark ? '#484F58' : '#9CA3AF',
            'circle-opacity': 0.5,
            'circle-stroke-width': 1,
            'circle-stroke-color': isDark ? '#161B22' : '#FFFFFF',
          },
        });
      }

      // 3. Pilot Stations (17 key corridor stations with dynamic queues)
      if (!map.getSource('stations')) {
        const list: Station[] = stationsRef.current.length > 0 ? stationsRef.current : initialStations;
        const stationGeoJSON: FeatureCollection = {
          type: 'FeatureCollection',
          features: list.map((s) => ({
            type: 'Feature',
            properties: {
              code: s.code,
              name: s.name,
              sequence: s.sequence,
              queue: currentQueuesRef.current[s.code] || 0,
            },
            geometry: {
              type: 'Point',
              coordinates: [s.lon, s.lat],
            },
          })),
        };

        map.addSource('stations', {
          type: 'geojson',
          data: stationGeoJSON,
        });

        // Station queue saturation dynamic halo
        map.addLayer({
          id: 'station-queue-halo',
          type: 'circle',
          source: 'stations',
          paint: {
            'circle-radius': [
              'interpolate',
              ['linear'],
              ['coalesce', ['get', 'queue'], 0],
              0, 10,
              80, 18,
              200, 32,
            ],
            'circle-color': [
              'step',
              ['coalesce', ['get', 'queue'], 0],
              '#2ECC71',
              80, '#F39C12',
              150, '#E74C3C',
            ],
            'circle-opacity': 0.45,
            'circle-stroke-width': 1.5,
            'circle-stroke-color': [
              'step',
              ['coalesce', ['get', 'queue'], 0],
              '#2ECC71',
              80, '#F39C12',
              150, '#E74C3C',
            ],
          },
        });

        // Center station dot
        map.addLayer({
          id: 'station-dot',
          type: 'circle',
          source: 'stations',
          paint: {
            'circle-radius': 6.5,
            'circle-color': isDark ? '#161B22' : '#FFFFFF',
            'circle-stroke-width': 2.5,
            'circle-stroke-color': '#E53935',
          },
        });

        // Station Labels
        map.addLayer({
          id: 'station-labels',
          type: 'symbol',
          source: 'stations',
          layout: {
            'text-field': ['get', 'name'],
            'text-size': 10.5,
            'text-offset': [0.9, 0],
            'text-anchor': 'left',
            'text-allow-overlap': false,
            'text-font': ['Noto Sans Regular'],
          },
          paint: {
            'text-color': isDark ? '#FFFFFF' : '#111827',
            'text-halo-color': isDark ? '#0E1117' : '#FFFFFF',
            'text-halo-width': 2,
          },
        });

        map.on('click', 'station-dot', (e: maplibregl.MapLayerMouseEvent) => {
          if (!e.features || !e.features[0]) return;
          const code = e.features[0].properties?.code;
          const st = (stationsRef.current.length > 0 ? stationsRef.current : initialStations).find(
            (s: Station) => s.code === code
          );
          if (st) {
            onSelectEntity({
              type: 'station',
              id: st.code,
              data: { ...st, queue: currentQueuesRef.current[st.code] || 0 },
            });
          }
        });

        map.on('mouseenter', 'station-dot', () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'station-dot', () => {
          map.getCanvas().style.cursor = '';
        });
      }

      // 4. Live Active Fleet (Buses - Placed ON TOP of infrastructure and stations)
      if (!map.getSource('active-buses')) {
        const initialBusGeojson: FeatureCollection = {
          type: 'FeatureCollection',
          features: activeBusesRef.current.map((b) => ({
            type: 'Feature',
            properties: {
              bus_id: b.bus_id,
              route: b.route,
              occupancy_pct: b.occupancy_pct,
              passengers: b.passengers,
              is_stopped: b.is_stopped ? 1 : 0,
            },
            geometry: {
              type: 'Point',
              coordinates: [b.lon, b.lat],
            },
          })),
        };

        map.addSource('active-buses', {
          type: 'geojson',
          data: initialBusGeojson,
        });

        // Bus bunching warning outer ring (4.3.2)
        map.addLayer({
          id: 'bus-bunching-ring',
          type: 'circle',
          source: 'active-buses',
          filter: ['==', ['get', 'is_bunching'], 1],
          paint: {
            'circle-radius': 22,
            'circle-color': '#E74C3C',
            'circle-opacity': 0.25,
            'circle-stroke-width': 2.2,
            'circle-stroke-color': '#F39C12',
          },
        });

        // Bus pulse glow halo (sized by typology)
        map.addLayer({
          id: 'bus-glow',
          type: 'circle',
          source: 'active-buses',
          paint: {
            'circle-radius': ['match', ['get', 'bus_type'], 'biarticulado', 20, 15],
            'circle-color': [
              'match',
              ['get', 'route'],
              'B13', '#E53935',
              'B18', '#1976D2',
              'B23', '#FFA000',
              'B27', '#8E24AA',
              'B74', '#00897B',
              'B75', '#D84315',
              '#E53935',
            ],
            'circle-opacity': 0.45,
            'circle-blur': 0.5,
          },
        });

        // Bus occupancy status outer ring (Green <60%, Yellow 60-85%, Red >=85%)
        map.addLayer({
          id: 'bus-occupancy-ring',
          type: 'circle',
          source: 'active-buses',
          paint: {
            'circle-radius': ['match', ['get', 'bus_type'], 'biarticulado', 13.5, 10.5],
            'circle-color': 'transparent',
            'circle-stroke-width': 2.2,
            'circle-stroke-color': [
              'step',
              ['get', 'occupancy_pct'],
              '#2ECC71',
              60, '#F1C40F',
              85, '#E74C3C',
            ],
            'circle-stroke-opacity': 0.95,
          },
        });

        // Biarticulado double-articulation joint outer ring
        map.addLayer({
          id: 'bus-biart-ring',
          type: 'circle',
          source: 'active-buses',
          filter: ['==', ['get', 'bus_type'], 'biarticulado'],
          paint: {
            'circle-radius': 16.5,
            'circle-color': 'transparent',
            'circle-stroke-width': 1.6,
            'circle-stroke-color': isDark ? '#FFFFFF' : '#1A202C',
            'circle-stroke-opacity': 0.75,
          },
        });

        // Bus main solid circle (Articulado: 7.5px, Biarticulado: 10.5px)
        map.addLayer({
          id: 'bus-dot',
          type: 'circle',
          source: 'active-buses',
          paint: {
            'circle-radius': ['match', ['get', 'bus_type'], 'biarticulado', 10.5, 7.5],
            'circle-color': [
              'match',
              ['get', 'route'],
              'B13', '#E53935',
              'B18', '#1976D2',
              'B23', '#FFA000',
              'B27', '#8E24AA',
              'B74', '#00897B',
              'B75', '#D84315',
              '#E53935',
            ],
            'circle-stroke-width': 2.0,
            'circle-stroke-color': isDark ? '#FFFFFF' : '#1A202C',
          },
        });

        // Bus Route label text
        map.addLayer({
          id: 'bus-label',
          type: 'symbol',
          source: 'active-buses',
          layout: {
            'text-field': ['get', 'route'],
            'text-size': ['match', ['get', 'bus_type'], 'biarticulado', 9.5, 8.0],
            'text-allow-overlap': true,
            'text-font': ['Noto Sans Bold'],
          },
          paint: {
            'text-color': '#FFFFFF',
            'text-halo-color': '#000000',
            'text-halo-width': 1.6,
          },
        });

        const handleBusClick = (e: maplibregl.MapLayerMouseEvent) => {
          if (!e.features || !e.features[0]) return;
          const bId = e.features[0].properties?.bus_id;
          const bus = activeBusesRef.current.find((b) => b.bus_id === bId);
          if (bus) {
            onSelectEntity({
              type: 'bus',
              id: bus.bus_id,
              data: bus,
            });
          }
        };

        ['bus-dot', 'bus-label', 'bus-occupancy-ring', 'bus-biart-ring', 'bus-glow'].forEach((layerId) => {
          map.on('click', layerId, handleBusClick);
          map.on('mouseenter', layerId, () => {
            map.getCanvas().style.cursor = 'pointer';
          });
          map.on('mouseleave', layerId, () => {
            map.getCanvas().style.cursor = '';
          });
        });
      }

      // Populate immediately with current simulation state
      updateBusesSource();
      updateStationsSource();

      // Smoothly fit view to the full Autonorte - Caracas pilot corridor
      map.fitBounds([[-74.072, 4.630], [-74.042, 4.758]], {
        padding: 50,
        duration: 800,
      });
    } catch (err: any) {
      console.error('[MapLibre] Error setting up operational layers:', err);
    }
  };

  // 60 FPS update of active buses and Camera Follow mode (4.3.3)
  useEffect(() => {
    updateBusesSource();

    if (isCameraFollowing && selectedEntity?.type === 'bus' && mapRef.current) {
      const targetBus = activeBusesRef.current.find((b) => b.bus_id === selectedEntity.id);
      if (targetBus) {
        mapRef.current.easeTo({
          center: [targetBus.lon, targetBus.lat],
          duration: 100,
          easing: (t) => t,
        });
      }
    }
  }, [activeBuses, isCameraFollowing, selectedEntity]);

  // Update stations when queues change
  useEffect(() => {
    updateStationsSource();
  }, [stations, currentQueues]);

  // Center on selected entity
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedEntity) return;

    if (selectedEntity.type === 'station') {
      const { lat, lon } = selectedEntity.data;
      map.flyTo({ center: [lon, lat], zoom: 14.8, speed: 1.2, curve: 1.4 });
    } else if (selectedEntity.type === 'bus') {
      const { lat, lon } = selectedEntity.data;
      map.flyTo({ center: [lon, lat], zoom: 15.0, speed: 1.2, curve: 1.4 });
    }
  }, [selectedEntity]);

  return (
    <div className="map-viewport-wrapper">
      <div ref={mapContainerRef} className="map-container" />
    </div>
  );
};
