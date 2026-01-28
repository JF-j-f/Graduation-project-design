-- ============================================
-- MusicMode Database Migration - Phase 1
-- Project: MusicMode (Python Backend/ML)
-- Purpose: Add fields for KKBOX data and recommendation algorithm
-- ============================================

USE musicweb;

-- ============================================
-- 1. Modify songs table - Add KKBOX fields
-- ============================================

-- Add kkbox_id: Store KKBOX original song ID
ALTER TABLE songs ADD COLUMN kkbox_id VARCHAR(50) NULL COMMENT 'KKBOX original song ID';

-- Add genre_ids: Store KKBOX original genre IDs (e.g. "465|458|1259")
ALTER TABLE songs ADD COLUMN genre_ids VARCHAR(100) NULL COMMENT 'KKBOX genre IDs separated by |';

-- Add language: Store language code
ALTER TABLE songs ADD COLUMN language VARCHAR(10) NULL COMMENT 'Language code';

-- Add popularity: Store song popularity score
ALTER TABLE songs ADD COLUMN popularity INT DEFAULT 0 COMMENT 'Popularity score based on KKBOX interactions';

-- ============================================
-- 2. Modify recommendations table
-- ============================================

-- Add source_type: Identify recommendation source (cold_start or deepfm)
ALTER TABLE recommendations ADD COLUMN source_type VARCHAR(20) DEFAULT 'deepfm' COMMENT 'Recommendation source type';

-- ============================================
-- 3. Create indexes for query performance
-- ============================================

CREATE INDEX idx_kkbox_id ON songs(kkbox_id);
CREATE INDEX idx_genre_ids ON songs(genre_ids);
CREATE INDEX idx_popularity ON songs(popularity DESC);

-- ============================================
-- 4. Verify migration results
-- ============================================

DESCRIBE songs;
DESCRIBE recommendations;
