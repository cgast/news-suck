"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import umap
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from shared.models.news import NewsItem, NewsItemSimilarity  # Updated import
from app.config import settings
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

async def generate_clusters(
    db: AsyncSession,
    hours: int = 48,
    min_similarity: float = 0.6
) -> Dict[int, List[dict]]:
    """Generate news clusters using Redis vector similarity."""
    try:
        # Get Redis client
        redis_client = await get_redis_client()
        
        # Generate clusters using Redis
        clusters = await redis_client.get_clusters(hours, min_similarity)
        
        if not clusters:
            logger.warning("No clusters found in Redis")
            return {}
            
        # Enrich cluster data with additional news item details from database
        enriched_clusters: Dict[int, List[dict]] = {}
        
        for cluster_id, items in clusters.items():
            # Get all news IDs in this cluster
            news_ids = [item['id'] for item in items]
            
            # Get full news items from database
            stmt = select(NewsItem).filter(NewsItem.id.in_(news_ids))
            result = await db.execute(stmt)
            news_items = {item.id: item for item in result.scalars().all()}
            
            # Create enriched items
            enriched_items = []
            for item in items:
                news_item = news_items.get(item['id'])
                if news_item:
                    enriched_items.append({
                        "id": news_item.id,
                        "title": news_item.title,
                        "summary": news_item.summary,
                        "url": news_item.url,
                        "source_url": news_item.source_url,
                        "first_seen_at": news_item.first_seen_at,
                        "last_seen_at": news_item.last_seen_at,
                        "hit_count": news_item.hit_count,
                        "created_at": news_item.created_at,
                        "updated_at": news_item.updated_at,
                        "similarity": item['similarity'],
                        "cluster_id": cluster_id
                    })
            
            if enriched_items:
                enriched_clusters[cluster_id] = enriched_items
        
        return enriched_clusters
        
    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise

async def generate_umap_visualization(
    db: AsyncSession,
    hours: int = 48,
    min_similarity: float = 0.6
) -> List[dict]:
    """Generate UMAP visualization data for news items."""
    try:
        # First generate clusters to get cluster assignments
        clusters = await generate_clusters(db, hours, min_similarity)
        
        # Create a mapping of news item ID to cluster ID
        item_to_cluster = {}
        for cluster_id, items in clusters.items():
            for item in items:
                item_to_cluster[item['id']] = int(cluster_id)

        # Get news items from the last n hours
        time_filter = datetime.utcnow() - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc()).limit(1000)  # Limit to 1000 items for performance
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            return []

        # Extract embeddings and create UMAP input
        embeddings = [item.embedding for item in news_items]
        
        # Perform UMAP dimensionality reduction
        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15)
        umap_result = reducer.fit_transform(embeddings)
        
        # Calculate time-based opacity
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        yesterday = now - timedelta(days=1)
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(news_items):
            # Calculate opacity based on age
            last_seen = news_item.last_seen_at
            if last_seen >= one_hour_ago:
                opacity = 0.8
            elif last_seen <= yesterday:
                opacity = 0.2
            else:
                # Linear interpolation between 0.8 and 0.2 for items between 1 hour and 1 day old
                hours_old = (now - last_seen).total_seconds() / 3600
                opacity = 0.8 - (0.6 * (hours_old - 1) / 23)  # 23 = 24 - 1
            
            visualization_data.append({
                "id": news_item.id,
                "title": news_item.title,
                "url": news_item.url,
                "source_url": news_item.source_url,
                "last_seen_at": news_item.last_seen_at.isoformat(),
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1]),
                "cluster_id": item_to_cluster.get(news_item.id),
                "opacity": opacity
            })
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}")
        raise
