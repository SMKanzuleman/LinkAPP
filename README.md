# 🔒 LinkAPP : Mini Messenger

[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Complete-green?style=for-the-badge)](https://github.com/username/SecureChat)
[![License](https://img.shields.io/github/license/username/SecureChat?style=for-the-badge)](LICENSE)
[![Core Security](https://img.shields.io/badge/Security-XOR%20%26%20SHA--256-purple?style=for-the-badge)](docs/security.md)

---

## 🚀 Introduction

LinkAPP is a full-featured chat application built using **Python Socket Programming**. It implements a **Hybrid Network Architecture** to ensure both reliability and speed, making it suitable for secure messaging and real-time voice/video.

---

## ✨ Core Feature Matrix

| Category | Features |
| :--- | :--- |
| **Messaging** | Private 1-to-1 Chat, Group Chat (PIN Secured), File Sharing (Max 5MB). |
| **Media** | Low-latency **Voice** and **Video** Calls, Group Conferencing. |
| **Data Protection** | XOR Encryption, SHA-256 Hashing, and Base64 Encoding. |

---

## 📐 System Architecture: Hybrid Protocol

The application runs on a Client-Server model, utilizing a two-pronged network approach:

1.  **TCP (Port 5556)**: The reliable layer for all control data (Authentication, Text, Group Management).
2.  **UDP (Ports 5557/5558)**: The fast layer, dedicated entirely to real-time media streams.



### Protocol Layer Security
All TCP messages are prefixed with a custom **10-byte fixed-length header**. This is critical for stream parsing, ensuring the server knows the exact length of the JSON payload and preventing message fragmentation.



---

## 🔒 Data Security Deep Dive

Data protection is paramount. Sensitive information is secured both during transmission and at rest:

* **Encryption**: Messages are scrambled using a **Simple XOR Cipher** before they are saved to the database.
* **Serialization**: Encrypted binary data is translated into safe ASCII text via **Base64** to ensure reliable storage in the SQLite `TEXT` fields.
* **Hashing**: User passwords are secured using the **SHA-256 hashing algorithm**.



---

## 🛠️ Technology Stack

| Component | Library/Tech | Function | Badge |
| :--- | :--- | :--- | :--- |
| **Networking** | `socket` | Direct control over TCP/UDP sockets. | [![Networking](https://img.shields.io/badge/Networking-Sockets-blue?style=flat&logo=python)](docs/tech.md) |
| **GUI** | `tkinter` | Cross-platform user interface. | [![GUI](https://img.shields.io/badge/Interface-Tkinter-yellow?style=flat)](docs/tech.md) |
| **Database** | `sqlite3` | Encrypted persistence for logs (`chat.db`). | [![Database](https://img.shields.io/badge/Database-SQLite-003B57?style=flat&logo=sqlite)](docs/tech.md) |
| **Media** | `OpenCV`, `PyAudio` | Handles camera and microphone streaming. | [![Media](https://img.shields.io/badge/Media-OpenCV%2FPyaudio-red?style=flat)](docs/tech.md) |

---

## ⚙️ Installation and Setup

### Prerequisites

You need **Python 3.9+** and must install the necessary media dependencies.

```bash
# Install required packages (PyAudio and OpenCV may need specific system dependencies)
pip install tkinter pyaudio opencv-python Pillow
