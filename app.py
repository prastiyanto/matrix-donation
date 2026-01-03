import streamlit as st
import pandas as pd
import gspread
import hashlib
from datetime import datetime
import os
import json
from google.oauth2.service_account import Credentials
# (Import duplikat dihapus agar rapi)

# --- Konfigurasi Halaman ---
st.set_page_config(page_title="Keanggotaan Matrix Donation", layout="wide")

# --- Fungsi Utility ---

@st.cache_resource
def init_connection():
    """
    Menginisialisasi koneksi ke Google Sheets menggunakan hybrid logic yang aman.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = None

    # 1. COBA CEK SECRETS (CLOUD)
    # Kita bungkus try-except agar tidak error "No secrets found" di Local
    try:
        if "gcp_service_account" in st.secrets:
            service_account_info = json.loads(st.secrets["gcp_service_account"])
            # Fix Newline untuk Cloud
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    except FileNotFoundError:
        # Ini terjadi jika secrets.toml tidak ada (di Local). Biarkan pass.
        pass
    except Exception as e:
        # Error lain pada secrets biarkan lewat dulu
        pass

    # 2. JIKA SECRETS GAGAL/TIDAK ADA, CEK LOCAL FILE
    if creds is None:
        if os.path.exists("credentials.json"):
            try:
                with open("credentials.json", "r") as f:
                    service_account_info = json.load(f)
                # Fix Newline untuk Local
                service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")
                creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            except Exception as e:
                st.error(f"❌ Error membaca credentials.json: {e}")
                return None

    # 3. FINALISASI KONEKSI
    if creds is None:
        st.error("⚠️ Tidak ditemukan kredensial! Pastikan ada 'secrets' (di Cloud) atau file 'credentials.json' (di Local).")
        return None

    try:
        gc = gspread.authorize(creds)
        # Buka Spreadsheet (Pastikan nama ini SESUAI dengan nama file di Google Drive)
        sh = gc.open("DB_MD") 
        return sh
    except Exception as e:
        st.error(f"❌ Gagal terhubung ke Google Sheets: {e}")
        return None

def hash_password(password):
    """Mengembalikan hash SHA-256 dari password."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- Load Database ---
sh = init_connection()

# --- Navigasi Sidebar ---
menu = st.sidebar.selectbox("Navigasi", ["Pendaftaran Anggota", "Login Admin"])

# --- Halaman Pendaftaran ---
if menu == "Pendaftaran Anggota":
    st.title("📝 Pendaftaran Anggota Baru")
    st.markdown("Silakan isi formulir di bawah ini dengan data yang valid.")
    
    with st.form(key="form_pendaftaran"):
        nama = st.text_input("Nama Lengkap")
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        no_wa = st.text_input("Nomor WhatsApp (Ex: 08123...)")
        link_profil = st.text_input("Link Profil (LinkedIn/Portfolio)")
        
        submit_btn = st.form_submit_button("Simpan Data")
        
        if submit_btn:
            # 1. Validasi Input
            if not (nama and username and email and password and no_wa and link_profil):
                st.warning("⚠️ Semua field wajib diisi!")
            else:
                if sh:
                    try:
                        # 2. Persiapan Data
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # [Nama, Username, Email, Password, No_WA, Link, Timestamp]
                        # Note: Password disimpan mentah sesuai request awal, atau hash jika mau aman
                        # Jika ingin hash: row_data = [nama, username, email, hash_password(password), no_wa, link_profil, timestamp]
                        row_data = [nama, username, email, password, no_wa, link_profil, timestamp]
                        
                        # 3. Kirim ke Google Sheet
                        worksheet = sh.sheet1
                        worksheet.append_row(row_data)
                        
                        # 4. Feedback Sukses
                        st.success("✅ Data berhasil disimpan! Terima kasih telah mendaftar.")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Terjadi kesalahan saat menyimpan data: {e}")
                else:
                    st.error("❌ Koneksi database tidak tersedia. Mohon cek konfigurasi.")

# --- Halaman Admin ---
elif menu == "Login Admin":
    st.title("🔐 Dashboard Admin")
    
    # Input Password Admin
    password_input = st.text_input("Masukkan Kode Akses Admin", type="password")
    
    # Cek Hash Password Admin
    password_hash = hashlib.sha256(password_input.encode()).hexdigest() if password_input else ""
    
    # Hash dari "admin123"
    if password_hash == "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9":
        st.success("Akses Diterima.")
        st.divider()
        st.subheader("Database Anggota")
        
        if sh:
            try:
                worksheet = sh.sheet1
                # Mengambil semua records
                data = worksheet.get_all_records()
                
                if data:
                    df = pd.DataFrame(data)
                    df.index = df.index + 1  # Mulai index dari 1
                    
                    # Privacy Rule: Hapus kolom password hash/password user jika ada agar admin tidak lihat
                    df_display = df.copy()
                    if 'Password' in df_display.columns: 
                        df_display = df_display.drop(columns=['Password']) # Hide password user
                    
                    st.dataframe(df_display, use_container_width=True)
                    st.info(f"Total Database: {len(df)} Anggota")
                    
                    st.divider()
                    
                    # --- CRUD Operations ---
                    tab_edit, tab_delete, tab_card = st.tabs(["✏️ Edit Data", "🗑️ Hapus Data", "📇 Cetak Kartu"])
                    
                    # --- 1. Edit Data ---
                    with tab_edit:
                        st.subheader("Edit Data Anggota")
                        
                        user_options = [f"{row['Username']} - {row['Nama']}" for index, row in df.iterrows()]
                        selected_user_str = st.selectbox("Pilih Anggota untuk Diedit", options=user_options, index=None, placeholder="Cari Username/Nama...")
                        
                        if selected_user_str:
                            selected_username = selected_user_str.split(" - ")[0]
                            selected_row = df[df['Username'] == selected_username].iloc[0]
                            
                            with st.form(key="form_edit"):
                                st.write(f"Editing: **{selected_row['Nama']}** ({selected_username})")
                                
                                new_nama = st.text_input("Nama Lengkap", value=selected_row['Nama'])
                                new_username_input = st.text_input("Username", value=selected_row['Username'])
                                new_email = st.text_input("Email", value=selected_row['Email'])
                                new_password_input = st.text_input("Password Baru (Biarkan kosong jika tidak diganti)", type="password")
                                new_no_wa = st.text_input("No WhatsApp", value=selected_row['No_WA'])
                                new_link = st.text_input("Link Profil", value=selected_row['Link'])
                                
                                btn_update = st.form_submit_button("Simpan Perubahan")
                                
                                if btn_update:
                                    try:
                                        cell_username = worksheet.find(selected_username)
                                        row_number = cell_username.row
                                        
                                        # Update cell (Urutan Kolom sesuaikan dengan header sheet)
                                        # Asumsi: [Nama, Username, Email, Password, No_WA, Link, Timestamp]
                                        # Col 1=Nama, 2=Username, 3=Email, 4=Password, 5=No_WA, 6=Link
                                        
                                        worksheet.update_cell(row_number, 1, new_nama) # Nama ada di kol 1 berdasarkan kode append
                                        worksheet.update_cell(row_number, 2, new_username_input)
                                        worksheet.update_cell(row_number, 3, new_email)
                                        
                                        if new_password_input:
                                            # Update password langsung (atau hash jika mau)
                                            worksheet.update_cell(row_number, 4, new_password_input)
                                            
                                        worksheet.update_cell(row_number, 5, new_no_wa)
                                        worksheet.update_cell(row_number, 6, new_link)
                                        
                                        st.success(f"Data {new_username_input} berhasil diperbarui!")
                                        st.rerun()
                                        
                                    except gspread.exceptions.CellNotFound:
                                        st.error("Error: Data tidak ditemukan di Spreadsheet.")
                                    except Exception as e:
                                        st.error(f"Gagal update data: {e}")

                    # --- 2. Hapus Data ---
                    with tab_delete:
                        st.subheader("Hapus Data Anggota")
                        st.warning("⚠️ Perhatian: Data yang dihapus tidak dapat dikembalikan.")
                        
                        delete_user_str = st.selectbox("Pilih Anggota untuk Dihapus", options=user_options, index=None, placeholder="Cari Username/Nama...", key="del_select")
                        
                        if delete_user_str:
                            delete_username = delete_user_str.split(" - ")[0]
                            
                            if st.button("🗑️ Hapus Anggota", type="primary"):
                                try:
                                    cell_username = worksheet.find(delete_username)
                                    row_number = cell_username.row
                                    
                                    worksheet.delete_rows(row_number)
                                    st.success(f"Anggota {delete_username} telah dihapus.")
                                    st.rerun()
                                    
                                except gspread.exceptions.CellNotFound:
                                    st.error("Error: User tidak ditemukan.")
                                except Exception as e:
                                    st.error(f"Gagal menghapus data: {e}")
                                    
                    # --- 3. Cetak Kartu ---
                    with tab_card:
                        st.subheader("📇 Generate Kartu Anggota")
                        
                        card_user_str = st.selectbox("Pilih Anggota untuk Cetak Kartu", options=user_options, index=None, placeholder="Cari Username/Nama...", key="card_select")
                        
                        if card_user_str:
                            card_username = card_user_str.split(" - ")[0]
                            # Ambil data terbaru dari dataframe
                            card_data = df[df['Username'] == card_username].iloc[0]
                            
                            if st.button("Generate Kartu"):
                                try:
                                    from PIL import Image, ImageDraw, ImageFont
                                    import io
                                    
                                    # --- UPDATE POSISI TEKS (Sesuaikan dengan gambar Anda) ---
                                    # Posisi X, Y (dalam pixel)
                                    POSISI_TEKS = {
                                        "nama": (700, 430),
                                        "username": (700, 610),
                                        "email": (700, 790),
                                        "password": (700, 970),
                                        "wa": (700, 1150),
                                        "link": (700, 1330)
                                    }
                                    
                                    # Nama file gambar harus SAMA PERSIS dengan yang diupload
                                    nama_file_gambar = "template_kartu.png"
                                    
                                    if not os.path.exists(nama_file_gambar):
                                        st.error(f"File '{nama_file_gambar}' tidak ditemukan di folder!")
                                        st.info("Pastikan file gambar sudah diupload ke folder project.")
                                    else:
                                        image = Image.open(nama_file_gambar)
                                        draw = ImageDraw.Draw(image)
                                        
                                        # Load Font
                                        try:
                                            # Gunakan roboto.ttf jika ada, atau default
                                            font = ImageFont.truetype("roboto.ttf", 70) # Ukuran font disesuaikan
                                        except IOError:
                                            font = ImageFont.load_default()
                                            st.warning("Font 'roboto.ttf' tidak ditemukan, menggunakan font default.")
                                            
                                        # Warna Teks (Ungu Gelap)
                                        text_color = "#1A0B2E"
                                        
                                        # Draw Data
                                        draw.text(POSISI_TEKS["nama"], str(card_data['Nama']), fill=text_color, font=font)
                                        draw.text(POSISI_TEKS["username"], str(card_data['Username']), fill=text_color, font=font)
                                        draw.text(POSISI_TEKS["email"], str(card_data['Email']), fill=text_color, font=font)
                                        draw.text(POSISI_TEKS["password"], f"{card_data['Password']}", fill=text_color, font=font)
                                        draw.text(POSISI_TEKS["wa"], str(card_data['No_WA']), fill=text_color, font=font)
                                        draw.text(POSISI_TEKS["link"], str(card_data['Link']), fill=text_color, font=font)
                                        
                                        # Tampilkan Preview
                                        st.image(image, caption="Preview Kartu Anggota", use_container_width=True)
                                        
                                        # Button Download
                                        buf = io.BytesIO()
                                        image.save(buf, format="PNG")
                                        byte_im = buf.getvalue()
                                        
                                        st.download_button(
                                            label="⬇️ Download Kartu (PNG)",
                                            data=byte_im,
                                            file_name=f"Kartu_{card_username}.PNG",
                                            mime="image/png"
                                        )
                                        
                                except ImportError:
                                    st.error("Library 'Pillow' belum terinstall.")
                                except Exception as e:
                                    st.error(f"Gagal generate kartu: {e}")

                else:
                    st.info("📂 Database masih kosong.")
                    
            except Exception as e:
                st.error(f"❌ Gagal memuat data tabel: {e}. Pastikan row pertama Spreadsheet adalah Header.")
    elif password_input:
        st.error("⛔ Password Salah!")
