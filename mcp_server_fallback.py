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



def interpret_query_with_llm(user_query: str) -> str:
    """Use LLM to interpret query and generate SQL"""
    schema_info = """
    Database Schema:
    - customers: CustomerId, FirstName, LastName, Company, Address, City, State, Country, PostalCode, Phone, Fax, Email
    - artists: ArtistId, Name
    - albums: AlbumId, Title, ArtistId
    - tracks: TrackId, Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice
    - genres: GenreId, Name
    - employees: EmployeeId, LastName, FirstName, Title, ReportsTo, BirthDate, HireDate, Address, City, State, Country
    - invoices: InvoiceId, CustomerId, InvoiceDate, BillingAddress, BillingCity, BillingState, BillingCountry, Total
    - invoice_items: InvoiceLineId, InvoiceId, TrackId, UnitPrice, Quantity
    """
    
    prompt = f"""
    Given this database schema:
    {schema_info}
    
    Convert this natural language query to SQL:
    "{user_query}"
    
    Rules:
    - Return ONLY the SQL query, no explanation
    - Use proper JOINs when needed
    - Limit results to 20 rows
    - Use LIKE with % wildcards for text searches
    - For location queries like "customers in New York", search City, State, and Country columns
    
    Examples:
    - "customers in New York" -> SELECT c.FirstName, c.LastName, c.City, c.State, c.Country FROM customers c WHERE c.City LIKE '%New York%' OR c.State LIKE '%New York%' OR c.Country LIKE '%New York%' LIMIT 20
    - "artists like metallica" -> SELECT a.Name as Artist FROM artists a WHERE a.Name LIKE '%metallica%' LIMIT 20
    - "rock songs" -> SELECT t.Name as Track, a.Name as Artist, g.Name as Genre FROM tracks t JOIN albums al ON t.AlbumId = al.AlbumId JOIN artists a ON al.ArtistId = a.ArtistId JOIN genres g ON t.GenreId = g.GenreId WHERE g.Name LIKE '%rock%' LIMIT 20
    
    SQL:
    """
    
    try:
        import google.generativeai as genai
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content(prompt)
        sql = response.text.strip()
        
        # Clean up the response (remove markdown formatting if present)
        if sql.startswith('```sql'):
            sql = sql[6:]
        if sql.startswith('```'):
            sql = sql[3:]
        if sql.endswith('```'):
            sql = sql[:-3]
        
        return sql.strip()
        
    except Exception as e:
        print(f"[MCP-SERVER] LLM interpretation failed: {e}")
        # Fallback to simple query
        return "SELECT a.Name as Artist FROM artists a LIMIT 20"

def generate_sql_from_keywords(user_query: str) -> str:
    """Generate SQL using LLM interpretation"""
    print(f"[MCP-SERVER] *** STARTING SQL GENERATION ***")
    print(f"[MCP-SERVER] Original query: '{user_query}'")
    
    # Use LLM to interpret the query
    sql = interpret_query_with_llm(user_query)
    
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