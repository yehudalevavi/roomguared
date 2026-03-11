#!/usr/bin/env python3
"""
Library of 20 famous short melodies for Room Guard motion alerts.

Each melody contains just the iconic opening bars — enough to be
instantly recognizable on a passive buzzer (~2–4 seconds each).
All compositions are in the public domain.
"""

import random

from buzzer import (
    NOTE_C4, NOTE_D4, NOTE_DS4, NOTE_E4, NOTE_F4, NOTE_FS4, NOTE_G4,
    NOTE_GS4, NOTE_A4, NOTE_B4,
    NOTE_C5, NOTE_CS5, NOTE_D5, NOTE_DS5, NOTE_E5, NOTE_F5, NOTE_FS5,
    NOTE_G5, NOTE_GS5, NOTE_A5, NOTE_B5,
    NOTE_C6, REST,
)

# Each entry: (display_name, [(frequency_hz, duration_seconds), ...])
# q = quarter, e = eighth, h = half, dq = dotted quarter, s = sixteenth
MOTION_MELODIES = [
    (
        "Twinkle Twinkle Little Star",
        # Traditional / Mozart Variations K.265 — C major
        [
            (NOTE_C4, 0.22), (NOTE_C4, 0.22), (NOTE_G4, 0.22), (NOTE_G4, 0.22),
            (NOTE_A4, 0.22), (NOTE_A4, 0.22), (NOTE_G4, 0.40), (REST, 0.06),
            (NOTE_F4, 0.22), (NOTE_F4, 0.22), (NOTE_E4, 0.22), (NOTE_E4, 0.22),
            (NOTE_D4, 0.22), (NOTE_D4, 0.22), (NOTE_C4, 0.40),
        ],
    ),
    (
        "Ode to Joy",
        # Beethoven — Symphony No. 9, 4th mvt — C major
        [
            (NOTE_E4, 0.22), (NOTE_E4, 0.22), (NOTE_F4, 0.22), (NOTE_G4, 0.22),
            (NOTE_G4, 0.22), (NOTE_F4, 0.22), (NOTE_E4, 0.22), (NOTE_D4, 0.22),
            (NOTE_C4, 0.22), (NOTE_C4, 0.22), (NOTE_D4, 0.22), (NOTE_E4, 0.22),
            (NOTE_E4, 0.30), (NOTE_D4, 0.12), (NOTE_D4, 0.40),
        ],
    ),
    (
        "Eine kleine Nachtmusik",
        # Mozart K.525, 1st mvt Allegro — G major, opening 4 bars
        # Verified from MIDI score, transposed down one octave for buzzer
        # q=0.30s, e=0.15s at ~200 BPM
        [
            # Bar 1: G(q) r(e) D(e) | G(q) r(e) D(e)
            (NOTE_G4, 0.30), (REST, 0.15), (NOTE_D4, 0.15),
            (NOTE_G4, 0.30), (REST, 0.15), (NOTE_D4, 0.15),
            # Bar 2: G(e) D(e) G(e) B(e) | D5(q) r(q)
            (NOTE_G4, 0.15), (NOTE_D4, 0.15), (NOTE_G4, 0.15), (NOTE_B4, 0.15),
            (NOTE_D5, 0.30), (REST, 0.30),
            # Bar 3: C5(q) r(e) A(e) | C5(q) r(e) A(e)
            (NOTE_C5, 0.30), (REST, 0.15), (NOTE_A4, 0.15),
            (NOTE_C5, 0.30), (REST, 0.15), (NOTE_A4, 0.15),
            # Bar 4: C5(e) A(e) F#(e) A(e) | D(q) r(q)
            (NOTE_C5, 0.15), (NOTE_A4, 0.15), (NOTE_FS4, 0.15), (NOTE_A4, 0.15),
            (NOTE_D4, 0.30), (REST, 0.30),
        ],
    ),
    (
        "Für Elise",
        # Beethoven — Bagatelle No. 25, A minor
        [
            (NOTE_E5, 0.15), (NOTE_DS5, 0.15),
            (NOTE_E5, 0.15), (NOTE_DS5, 0.15),
            (NOTE_E5, 0.15), (NOTE_B4, 0.15), (NOTE_D5, 0.15), (NOTE_C5, 0.15),
            (NOTE_A4, 0.30), (REST, 0.06),
            (NOTE_E4, 0.15), (NOTE_A4, 0.15), (NOTE_B4, 0.30), (REST, 0.06),
            (NOTE_E4, 0.15), (NOTE_C5, 0.15), (NOTE_B4, 0.15), (NOTE_A4, 0.30),
        ],
    ),
    (
        "Happy Birthday",
        # Traditional — C major, two phrases
        [
            (NOTE_G4, 0.15), (NOTE_G4, 0.15),
            (NOTE_A4, 0.28), (NOTE_G4, 0.28), (NOTE_C5, 0.28), (NOTE_B4, 0.50),
            (REST, 0.06),
            (NOTE_G4, 0.15), (NOTE_G4, 0.15),
            (NOTE_A4, 0.28), (NOTE_G4, 0.28), (NOTE_D5, 0.28), (NOTE_C5, 0.50),
        ],
    ),
    (
        "Jingle Bells",
        # Traditional — C major, chorus
        [
            (NOTE_E4, 0.22), (NOTE_E4, 0.22), (NOTE_E4, 0.40), (REST, 0.06),
            (NOTE_E4, 0.22), (NOTE_E4, 0.22), (NOTE_E4, 0.40), (REST, 0.06),
            (NOTE_E4, 0.22), (NOTE_G4, 0.22), (NOTE_C4, 0.22), (NOTE_D4, 0.22),
            (NOTE_E4, 0.50),
        ],
    ),
    (
        "Mary Had a Little Lamb",
        # Traditional — C major
        [
            (NOTE_E4, 0.22), (NOTE_D4, 0.22), (NOTE_C4, 0.22), (NOTE_D4, 0.22),
            (NOTE_E4, 0.22), (NOTE_E4, 0.22), (NOTE_E4, 0.40), (REST, 0.06),
            (NOTE_D4, 0.22), (NOTE_D4, 0.22), (NOTE_D4, 0.40), (REST, 0.06),
            (NOTE_E4, 0.22), (NOTE_G4, 0.22), (NOTE_G4, 0.40),
        ],
    ),
    (
        "London Bridge",
        # Traditional — C major
        [
            (NOTE_G4, 0.28), (NOTE_A4, 0.15), (NOTE_G4, 0.22), (NOTE_F4, 0.22),
            (NOTE_E4, 0.22), (NOTE_F4, 0.22), (NOTE_G4, 0.35), (REST, 0.06),
            (NOTE_D4, 0.22), (NOTE_E4, 0.22), (NOTE_F4, 0.35), (REST, 0.06),
            (NOTE_E4, 0.22), (NOTE_F4, 0.22), (NOTE_G4, 0.35),
        ],
    ),
    (
        "Frère Jacques",
        # Traditional French — C major
        [
            (NOTE_C4, 0.22), (NOTE_D4, 0.22), (NOTE_E4, 0.22), (NOTE_C4, 0.22),
            (NOTE_C4, 0.22), (NOTE_D4, 0.22), (NOTE_E4, 0.22), (NOTE_C4, 0.22),
            (NOTE_E4, 0.22), (NOTE_F4, 0.22), (NOTE_G4, 0.40),
            (NOTE_E4, 0.22), (NOTE_F4, 0.22), (NOTE_G4, 0.40),
        ],
    ),
    (
        "Beethoven's Fifth",
        # Beethoven — Symphony No. 5, C minor, opening motif
        [
            (REST, 0.12),
            (NOTE_G4, 0.15), (NOTE_G4, 0.15), (NOTE_G4, 0.15),
            (NOTE_DS4, 0.65),
            (REST, 0.15),
            (NOTE_F4, 0.15), (NOTE_F4, 0.15), (NOTE_F4, 0.15),
            (NOTE_D4, 0.65),
        ],
    ),
    (
        "Canon in D",
        # Pachelbel — D major, the famous melody line
        [
            (NOTE_FS5, 0.28), (NOTE_E5, 0.28),
            (NOTE_D5, 0.28), (NOTE_CS5, 0.28),
            (NOTE_B4, 0.28), (NOTE_A4, 0.28),
            (NOTE_B4, 0.28), (NOTE_CS5, 0.28),
        ],
    ),
    (
        "Brahms' Lullaby",
        # Brahms — Wiegenlied Op. 49, C major
        [
            (NOTE_E4, 0.15), (NOTE_E4, 0.15),
            (NOTE_G4, 0.38), (REST, 0.06),
            (NOTE_E4, 0.15), (NOTE_E4, 0.15),
            (NOTE_G4, 0.38), (REST, 0.06),
            (NOTE_E4, 0.15), (NOTE_G4, 0.15),
            (NOTE_C5, 0.22), (NOTE_B4, 0.12), (NOTE_A4, 0.38),
        ],
    ),
    (
        "William Tell Overture",
        # Rossini — finale gallop
        [
            (NOTE_E4, 0.08), (NOTE_E4, 0.08), (NOTE_E4, 0.22), (REST, 0.04),
            (NOTE_E4, 0.08), (NOTE_E4, 0.08), (NOTE_E4, 0.22), (REST, 0.04),
            (NOTE_E4, 0.08), (NOTE_E4, 0.08), (NOTE_E4, 0.08),
            (NOTE_E4, 0.08), (NOTE_E4, 0.22), (REST, 0.06),
            (NOTE_A4, 0.12), (NOTE_CS5, 0.12), (NOTE_A4, 0.12),
            (NOTE_CS5, 0.12), (NOTE_A4, 0.12), (NOTE_CS5, 0.12),
            (NOTE_E5, 0.35),
        ],
    ),
    (
        "La Cucaracha",
        # Mexican traditional — C major
        [
            (NOTE_C4, 0.12), (NOTE_C4, 0.12), (NOTE_C4, 0.12),
            (NOTE_F4, 0.22), (NOTE_A4, 0.35), (REST, 0.06),
            (NOTE_C4, 0.12), (NOTE_C4, 0.12), (NOTE_C4, 0.12),
            (NOTE_F4, 0.22), (NOTE_A4, 0.35), (REST, 0.06),
            (NOTE_F4, 0.18), (NOTE_F4, 0.18), (NOTE_E4, 0.18), (NOTE_E4, 0.18),
            (NOTE_D4, 0.18), (NOTE_D4, 0.18), (NOTE_C4, 0.35),
        ],
    ),
    (
        "When the Saints Go Marching In",
        # Traditional — C major
        [
            (NOTE_C4, 0.20), (NOTE_E4, 0.20), (NOTE_F4, 0.20), (NOTE_G4, 0.50),
            (REST, 0.08),
            (NOTE_C4, 0.20), (NOTE_E4, 0.20), (NOTE_F4, 0.20), (NOTE_G4, 0.50),
            (REST, 0.08),
            (NOTE_C4, 0.20), (NOTE_E4, 0.20), (NOTE_F4, 0.20),
            (NOTE_G4, 0.22), (NOTE_E4, 0.22), (NOTE_C4, 0.22),
            (NOTE_E4, 0.22), (NOTE_D4, 0.40),
        ],
    ),
    (
        "Row Row Row Your Boat",
        # Traditional — C major, 6/8 time
        [
            (NOTE_C4, 0.28), (NOTE_C4, 0.28),
            (NOTE_C4, 0.20), (NOTE_D4, 0.12), (NOTE_E4, 0.28), (REST, 0.04),
            (NOTE_E4, 0.20), (NOTE_D4, 0.12), (NOTE_E4, 0.20), (NOTE_F4, 0.12),
            (NOTE_G4, 0.45),
        ],
    ),
    (
        "Yankee Doodle",
        # Traditional American — G major
        [
            (NOTE_G4, 0.15), (NOTE_G4, 0.15), (NOTE_A4, 0.15), (NOTE_B4, 0.15),
            (NOTE_G4, 0.15), (NOTE_B4, 0.15), (NOTE_A4, 0.30), (REST, 0.04),
            (NOTE_G4, 0.15), (NOTE_G4, 0.15), (NOTE_A4, 0.15), (NOTE_B4, 0.15),
            (NOTE_G4, 0.30), (NOTE_FS4, 0.30),
        ],
    ),
    (
        "Oh! Susanna",
        # Stephen Foster — C major
        [
            (NOTE_C4, 0.15), (NOTE_D4, 0.15),
            (NOTE_E4, 0.22), (NOTE_G4, 0.22),
            (NOTE_G4, 0.15), (NOTE_A4, 0.15),
            (NOTE_G4, 0.22), (NOTE_E4, 0.22),
            (NOTE_C4, 0.15), (NOTE_D4, 0.15),
            (NOTE_E4, 0.22), (NOTE_E4, 0.22),
            (NOTE_D4, 0.22), (NOTE_C4, 0.22), (NOTE_D4, 0.40),
        ],
    ),
    (
        "Greensleeves",
        # Traditional English — A minor, 3/4 time
        [
            (NOTE_A4, 0.25),
            (NOTE_C5, 0.25), (NOTE_D5, 0.25),
            (NOTE_E5, 0.32), (NOTE_F5, 0.12), (NOTE_E5, 0.25),
            (NOTE_D5, 0.25), (NOTE_B4, 0.32), (NOTE_GS4, 0.12),
            (NOTE_A4, 0.25), (NOTE_B4, 0.25), (NOTE_C5, 0.25),
            (NOTE_A4, 0.32), (NOTE_GS4, 0.12), (NOTE_A4, 0.25),
            (NOTE_B4, 0.25), (NOTE_GS4, 0.25), (NOTE_E4, 0.38),
        ],
    ),
    (
        "Old MacDonald Had a Farm",
        # Traditional — C major
        [
            (NOTE_C5, 0.22), (NOTE_C5, 0.22), (NOTE_C5, 0.22), (NOTE_G4, 0.22),
            (NOTE_A4, 0.22), (NOTE_A4, 0.22), (NOTE_G4, 0.40), (REST, 0.06),
            (NOTE_E4, 0.22), (NOTE_E4, 0.22), (NOTE_D4, 0.22), (NOTE_D4, 0.22),
            (NOTE_C4, 0.40),
        ],
    ),
]


def get_random_melody() -> tuple[str, list[tuple[float, float]]]:
    """Return a random (name, notes) tuple from the melody library."""
    return random.choice(MOTION_MELODIES)
