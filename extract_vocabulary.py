#!/usr/bin/env python3
import sqlite3
import json

def extract_vocabulary():
    """Extract all names from database for vocabulary"""
    conn = sqlite3.connect("chinook.db")
    cursor = conn.cursor()
    
    vocabulary = set()
    
    # Get all artist names
    cursor.execute("SELECT Name FROM artists")
    for row in cursor.fetchall():
        name = row[0].lower()
        vocabulary.add(name)
        # Add individual words from artist names
        for word in name.split():
            if len(word) > 2:
                vocabulary.add(word)
    
    # Get all album titles
    cursor.execute("SELECT Title FROM albums")
    for row in cursor.fetchall():
        title = row[0].lower()
        vocabulary.add(title)
        # Add individual words from album titles
        for word in title.split():
            if len(word) > 2:
                vocabulary.add(word)
    
    # Get all track names
    cursor.execute("SELECT Name FROM tracks")
    for row in cursor.fetchall():
        name = row[0].lower()
        vocabulary.add(name)
        # Add individual words from track names
        for word in name.split():
            if len(word) > 2:
                vocabulary.add(word)
    
    # Get all genre names
    cursor.execute("SELECT Name FROM genres")
    for row in cursor.fetchall():
        name = row[0].lower()
        vocabulary.add(name)
    
    conn.close()
    
    # Add music-related and database-related keywords
    database_keywords = [
        'artist', 'singer', 'band', 'musician', 'album', 'song', 'track', 'music',
        'rock', 'jazz', 'pop', 'metal', 'blues', 'classical', 'country', 'playlist',
        'genre', 'composer', 'performer', 'vocalist', 'group', 'duo', 'trio',
        'customers', 'customer', 'client', 'buyer', 'people', 'person',
        'employees', 'employee', 'staff', 'worker',
        'invoices', 'invoice', 'bill', 'payment', 'purchase',
        'city', 'state', 'country', 'address', 'location',
        'new', 'york', 'usa', 'america', 'canada', 'brazil', 'germany', 'france',
        '2007', '2008', '2009', '2010', '2011', '2012', '2013', 'year', 'date'
    ]
    
    vocabulary.update(database_keywords)
    
    # Convert to sorted list
    vocabulary_list = sorted(list(vocabulary))
    
    print(f"Extracted {len(vocabulary_list)} vocabulary terms")
    print("Sample terms:", vocabulary_list[:20])
    
    return vocabulary_list

if __name__ == "__main__":
    vocab = extract_vocabulary()
    
    # Save to file
    with open("vocabulary.json", "w") as f:
        json.dump(vocab, f, indent=2)
    
    print(f"Vocabulary saved to vocabulary.json with {len(vocab)} terms")