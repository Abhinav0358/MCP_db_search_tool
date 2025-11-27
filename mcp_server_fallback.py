#!/usr/bin/env python3
import asyncio
import json
import sqlite3
import os
import re
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Database path
DB_PATH = "chinook.db"

print(f"[DEBUG] Starting MCP server with database: {DB_PATH}")

def get_db_schema():
    """Get database schema for context"""
    return """
    Database Schema:
    - artists: ArtistId, Name
    - albums: AlbumId, Title, ArtistId
    - tracks: TrackId, Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice
    - genres: GenreId, Name
    - customers: CustomerId, FirstName, LastName, Company, Address, City, State, Country, PostalCode, Phone, Fax, Email, SupportRepId
    """

def execute_sql_query(query: str) -> List[Dict[str, Any]]:
    """Execute SQL query and return results"""
    print(f"[DEBUG] Executing SQL query: {query}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        print(f"[DEBUG] Query returned {len(results)} results")
        return results
        
    except Exception as e:
        print(f"[DEBUG] SQL Error: {str(e)}")
        return [{"error": str(e)}]



def generate_sql_from_keywords(user_query: str) -> str:
    """Generate SQL using keyword matching patterns"""
    print(f"[MCP-SERVER] *** STARTING SQL GENERATION ***")
    print(f"[MCP-SERVER] Original query: '{user_query}'")
    
    # Spell correction is now handled by the web app layer
    query_lower = user_query.lower().replace("'", "").replace('"', '')
    print(f"[MCP-SERVER] Cleaned query: '{query_lower}'")
    
    # Pattern matching for different query types
    artist_keywords = ['artist', 'singer', 'band', 'musician', 'performer', 'vocalist', 'composer', 'group', 'duo', 'trio']
    genre_keywords_extended = {
        'rock': 'Rock', 'metal': 'Metal', 'jazz': 'Jazz', 'pop': 'Pop', 'blues': 'Blues', 'classical': 'Classical',
        'country': 'Country', 'folk': 'Folk', 'punk': 'Punk', 'reggae': 'Reggae', 'electronic': 'Electronic',
        'dance': 'Dance', 'alternative': 'Alternative', 'indie': 'Alternative', 'grunge': 'Rock',
        'funk': 'Funk', 'soul': 'Soul', 'gospel': 'Gospel', 'opera': 'Classical'
    }
    
    if any(word in query_lower for word in artist_keywords):
        if any(word in query_lower for word in genre_keywords_extended.keys()):
            # Artists by genre
            for keyword, genre in genre_keywords_extended.items():
                if keyword in query_lower:
                    sql = f"SELECT DISTINCT a.Name as Artist, g.Name as Genre, COUNT(t.TrackId) as TrackCount FROM artists a JOIN albums al ON a.ArtistId = al.ArtistId JOIN tracks t ON al.AlbumId = t.AlbumId JOIN genres g ON t.GenreId = g.GenreId WHERE g.Name LIKE '%{genre}%' GROUP BY a.ArtistId, a.Name, g.Name ORDER BY TrackCount DESC LIMIT 20"
                    print(f"[MCP-SERVER] Matched genre pattern: {keyword} -> {genre}")
                    print(f"[MCP-SERVER] Generated SQL: {sql}")
                    return sql
        
        # Search for specific artist names
        stop_words = ['the', 'and', 'who', 'sing', 'artist', 'singer', 'band', 'musician', 'performer', 'by', 'from', 'with']
        artist_words = [word for word in query_lower.split() if len(word) > 2 and word not in stop_words]
        if artist_words:
            search_term = artist_words[0].replace("'", "").replace('"', '')
            sql = f"SELECT a.Name as Artist, COUNT(al.AlbumId) as Albums, COUNT(t.TrackId) as Tracks FROM artists a LEFT JOIN albums al ON a.ArtistId = al.ArtistId LEFT JOIN tracks t ON al.AlbumId = t.AlbumId WHERE a.Name LIKE '%{search_term}%' GROUP BY a.ArtistId, a.Name ORDER BY Albums DESC LIMIT 20"
            print(f"[MCP-SERVER] Matched artist search: {search_term}")
            print(f"[MCP-SERVER] Generated SQL: {sql}")
            return sql
    
    elif any(word in query_lower for word in ['album', 'record', 'disc', 'cd', 'vinyl', 'lp', 'ep', 'release']):
        # Album searches
        album_stop_words = ['the', 'and', 'album', 'record', 'disc', 'cd', 'vinyl', 'lp', 'ep', 'release', 'by', 'from']
        album_words = [word for word in query_lower.split() if len(word) > 2 and word not in album_stop_words]
        if album_words:
            search_term = album_words[0].replace("'", "").replace('"', '')
            return f"SELECT al.Title as Album, a.Name as Artist, COUNT(t.TrackId) as Tracks FROM albums al JOIN artists a ON al.ArtistId = a.ArtistId LEFT JOIN tracks t ON al.AlbumId = t.AlbumId WHERE al.Title LIKE '%{search_term}%' OR a.Name LIKE '%{search_term}%' GROUP BY al.AlbumId, al.Title, a.Name ORDER BY Tracks DESC LIMIT 20"
    
    elif any(word in query_lower for word in ['track', 'song', 'music', 'tune', 'melody', 'hit', 'single']):
        # Track searches
        if any(word in query_lower for word in ['long', 'duration', 'minute']):
            return "SELECT t.Name as Track, a.Name as Artist, al.Title as Album, ROUND(t.Milliseconds/60000.0, 2) as Minutes FROM tracks t JOIN albums al ON t.AlbumId = al.AlbumId JOIN artists a ON al.ArtistId = a.ArtistId WHERE t.Milliseconds > 300000 ORDER BY t.Milliseconds DESC LIMIT 20"
        
        track_stop_words = ['the', 'and', 'track', 'song', 'music', 'tune', 'melody', 'hit', 'single', 'by', 'from']
        track_words = [word for word in query_lower.split() if len(word) > 2 and word not in track_stop_words]
        if track_words:
            search_term = track_words[0].replace("'", "").replace('"', '')
            return f"SELECT t.Name as Track, a.Name as Artist, al.Title as Album, g.Name as Genre FROM tracks t JOIN albums al ON t.AlbumId = al.AlbumId JOIN artists a ON al.ArtistId = a.ArtistId LEFT JOIN genres g ON t.GenreId = g.GenreId WHERE t.Name LIKE '%{search_term}%' ORDER BY t.Name LIMIT 20"
    
    elif any(word in query_lower for word in ['genre', 'style', 'type']):
        # Genre searches
        return "SELECT g.Name as Genre, COUNT(t.TrackId) as TrackCount FROM genres g LEFT JOIN tracks t ON g.GenreId = t.GenreId GROUP BY g.GenreId, g.Name ORDER BY TrackCount DESC LIMIT 20"
    
    elif any(word in query_lower for word in ['country', 'indian', 'american', 'british', 'brazilian', 'canadian', 'australian', 'german', 'french', 'italian']):
        # Country-based searches (using customer data as proxy)
        country_keywords = {
            'indian': 'India', 'american': 'USA', 'british': 'United Kingdom', 'brazilian': 'Brazil',
            'canadian': 'Canada', 'australian': 'Australia', 'german': 'Germany', 'french': 'France',
            'italian': 'Italy', 'spanish': 'Spain', 'japanese': 'Japan', 'korean': 'South Korea'
        }
        
        for keyword, country in country_keywords.items():
            if keyword in query_lower:
                return f"SELECT c.Country, COUNT(*) as CustomerCount FROM customers c WHERE c.Country LIKE '%{country}%' GROUP BY c.Country LIMIT 20"
    
    # Default: search all artists
    search_words = [word for word in query_lower.split() if len(word) > 2]
    if search_words:
        search_term = search_words[0].replace("'", "").replace('"', '')
        return f"SELECT a.Name as Artist, COUNT(al.AlbumId) as Albums FROM artists a LEFT JOIN albums al ON a.ArtistId = al.ArtistId WHERE a.Name LIKE '%{search_term}%' GROUP BY a.ArtistId, a.Name ORDER BY Albums DESC LIMIT 20"
    
    # Fallback: show popular artists
    sql = "SELECT a.Name as Artist, COUNT(al.AlbumId) as Albums, COUNT(t.TrackId) as Tracks FROM artists a LEFT JOIN albums al ON a.ArtistId = al.ArtistId LEFT JOIN tracks t ON al.AlbumId = t.AlbumId GROUP BY a.ArtistId, a.Name ORDER BY Albums DESC, Tracks DESC LIMIT 20"
    print(f"[MCP-SERVER] Using fallback query")
    print(f"[MCP-SERVER] Generated SQL: {sql}")
    return sql

# Initialize MCP server
server = Server("chinook-search")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="search_music_database",
            description="Search the Chinook music database using natural language queries. Can find artists, songs, albums, genres, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query (e.g., 'rock artists', 'albums by metallica', 'long songs')"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    print(f"[MCP-SERVER] *** RECEIVED TOOL CALL ***")
    print(f"[MCP-SERVER] Tool name: {name}")
    print(f"[MCP-SERVER] Arguments: {arguments}")
    
    if name == "search_music_database":
        user_query = arguments.get("query", "")
        
        if not user_query:
            return [TextContent(type="text", text="Please provide a search query")]
        
        # Generate SQL from keywords
        sql_query = generate_sql_from_keywords(user_query)
        
        # Execute the query
        results = execute_sql_query(sql_query)
        
        # Format results
        if not results:
            response = "No results found for your query."
        elif "error" in results[0]:
            response = f"Error: {results[0]['error']}"
        else:
            response = f"Found {len(results)} results for '{user_query}':\n\n"
            for i, result in enumerate(results[:10], 1):  # Show max 10 results
                response += f"{i}. "
                response += " | ".join([f"{k}: {v}" for k, v in result.items() if v is not None])
                response += "\n"
        
        print(f"[MCP-SERVER] *** SENDING RESPONSE ***")
        print(f"[MCP-SERVER] Response length: {len(response)} characters")
        print(f"[MCP-SERVER] Response preview: {response[:100]}...")
        return [TextContent(type="text", text=response)]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Main server function"""
    print("[DEBUG] Starting MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    print("[DEBUG] Running MCP server")
    asyncio.run(main())