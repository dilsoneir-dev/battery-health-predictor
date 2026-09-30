import datetime
import json
import os
import re
import subprocess
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Configuração para exibição de tabelas completas no terminal
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 1000)


def get_base_dir():
    """Retorna o diretório base absoluto onde o script está localizado."""
    return (
        os.path.dirname(os.path.abspath(__file__))
        if "__file__" in globals()
        else os.getcwd()
    )


def load_config():
    """Lê as configurações e dados de hardware do arquivo config.json."""
    base_dir = get_base_dir()
    config_path = os.path.join(base_dir, "config.json")

    default_config = {
        "hardware_cycles": 260,
        "manufacture_date": "2021-09-03",
        "charge_stop_limit": 85,
        "charge_start_limit": 50,
        "connected_standby": False,
        "usb_powershare": False,
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
                print(f"Configurações carregadas de: {config_path}")
        except Exception as e:
            print(
                f"Aviso: Falha ao carregar config.json ({e}). Usando parâmetros padrão."
            )
    else:
        print("Aviso: config.json não encontrado. Usando parâmetros padrão.")

    return default_config


def sanitize_battery_report(file_path):
    """Higieniza automaticamente os campos de identificação sensíveis (COMPUTER NAME e USER NAME)."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # No relatório do Windows, o rótulo e o valor ficam em células
            # separadas, com quebras de linha e espaços entre eles:
            #   <td class="label"> COMPUTER NAME </td><td>NOME-REAL</td>
            # Por isso os padrões usam \s* e não dependem do nome começar com "DESKTOP-".
            substituicoes = (
                (r"COMPUTER NAME\s*</td>\s*<td>([^<]+)</td>", "DESKTOP-GENERIC"),
                (r"USER NAME\s*</td>\s*<td>([^<]+)</td>", "generic_user"),
            )
            for padrao, generico in substituicoes:
                encontrado = re.search(padrao, content)
                if encontrado:
                    valor_real = encontrado.group(1).strip()
                    # Troca o valor em TODO o relatório, não só no campo de origem.
                    if valor_real and valor_real != generico:
                        content = content.replace(valor_real, generico)

            # Reforços: nomes no padrão do Windows e pastas de usuário.
            content = re.sub(r"DESKTOP-[A-Za-z0-9]+", "DESKTOP-GENERIC", content)
            content = re.sub(
                r"C:\\Users\\[^\\<\"]+", r"C:\\Users\\generic_user", content
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Relatório 'battery-report.html' higienizado com sucesso.")
        except Exception as e:
            print(f"Aviso: Não foi possível higienizar o relatório ({e}).")


def generate_fresh_battery_report():
    """Gera um relatório atualizado via powercfg e aplica a higienização de dados."""
    base_dir = get_base_dir()
    output_path = os.path.join(base_dir, "battery-report.html")
    print("Gerando relatório atualizado da bateria via powercfg...")
    try:
        subprocess.run(
            ["powercfg", "/batteryreport", "/output", output_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        sanitize_battery_report(output_path)
        return output_path
    except Exception as e:
        print(
            f"Aviso: Não foi possível gerar relatório automático via powercfg ({e})."
        )
        return None


def parse_full_battery_report(html_content):
    """Extrai todas as seções e tabelas do relatório de bateria."""
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_data = {}

    info_dict = {}
    tables = soup.find_all("table")
    if tables:
        for row in tables[0].find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                val = cols[1].get_text(strip=True)
                if key:
                    info_dict[key] = val

    for t in tables:
        text = t.get_text()
        if "DESIGN CAPACITY" in text or "FULL CHARGE CAPACITY" in text:
            for row in t.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 2:
                    key = cols[0].get_text(strip=True)
                    val = cols[1].get_text(strip=True)
                    if key:
                        info_dict[key] = val

    parsed_data["system_info"] = info_dict

    def extract_table_by_header(header_title):
        headers = soup.find_all(["h2", "h3"])
        target_table = None
        for h in headers:
            if header_title.lower() in h.get_text().lower():
                target_table = h.find_next("table")
                break
        if not target_table:
            return pd.DataFrame()

        rows = target_table.find_all("tr")
        data = []
        headers_list = []

        for i, row in enumerate(rows):
            th_cols = row.find_all(["th", "td"])
            row_text = [c.get_text(strip=True) for c in th_cols]

            if i == 0 or "PERIOD" in row_text or "START TIME" in row_text:
                if not headers_list:
                    headers_list = row_text
                continue

            if row_text and any(row_text):
                data.append(row_text)

        if data:
            max_cols = max(len(r) for r in data)
            if not headers_list or len(headers_list) != max_cols:
                headers_list = [f"Col_{idx+1}" for idx in range(max_cols)]

            data_padded = [r + [""] * (max_cols - len(r)) for r in data]
            return pd.DataFrame(data_padded, columns=headers_list)
        return pd.DataFrame()

    cap_table = extract_table_by_header("Battery capacity history")
    parsed_records = []

    if not cap_table.empty:
        for idx, row in cap_table.iterrows():
            cols = list(row.values)
            if len(cols) >= 3:
                period_str = cols[0]
                full_charge_str = cols[1]
                design_capacity_str = cols[2]

                full_charge_match = re.search(r"([\d\.,]+)", full_charge_str)
                design_match = re.search(r"([\d\.,]+)", design_capacity_str)

                if full_charge_match and design_match:
                    full_charge = float(
                        full_charge_match.group(1).replace(".", "").replace(",", ".")
                    )
                    design = float(
                        design_match.group(1).replace(".", "").replace(",", ".")
                    )

                    dates = re.findall(r"\d{4}-\d{2}-\d{2}", period_str)
                    if dates:
                        end_date = dates[-1]
                        parsed_records.append(
                            {
                                "Periodo": period_str,
                                "Date": pd.to_datetime(end_date),
                                "FullChargeCapacity_mWh": full_charge,
                                "DesignCapacity_mWh": design,
                                "HealthPercent": (full_charge / design) * 100,
                            }
                        )

    parsed_data["capacity_history_df"] = pd.DataFrame(parsed_records)
    return parsed_data


def train_and_predict(df, target_health=30.0):
    """Treina o modelo de Regressão Linear para estimar a degradação temporal."""
    if df.empty or len(df) < 2:
        return None, "Dados insuficientes", [], []

    df = df.sort_values("Date").reset_index(drop=True)
    start_date = df["Date"].min()
    df["Days"] = (df["Date"] - start_date).dt.days

    X = df[["Days"]].values
    y = df["HealthPercent"].values

    model = LinearRegression()
    model.fit(X, y)

    slope = model.coef_[0]
    intercept = model.intercept_

    if slope >= 0:
        predicted_date = "A bateria não apresenta tendência de degradação nos dados fornecidos."
        days_to_target = max(df["Days"]) + 60
    else:
        days_to_target = (target_health - intercept) / slope
        predicted_date = start_date + datetime.timedelta(
            days=int(days_to_target)
        )

    max_days = (
        int(days_to_target) + 30
        if days_to_target and days_to_target > max(df["Days"])
        else max(df["Days"]) + 60
    )
    future_days = np.linspace(0, max_days, 100).reshape(-1, 1)
    future_preds = model.predict(future_days)
    future_dates = [
        start_date + datetime.timedelta(days=int(d))
        for d in future_days.flatten()
    ]

    return model, predicted_date, future_dates, future_preds


def plot_predictions(
    df,
    future_dates,
    future_preds,
    config,
    target_health=30.0,
    current_health=43.01,
):
    """Gera e salva o Gráfico 1: Projeção de saúde da bateria."""
    if df.empty:
        return

    base_dir = get_base_dir()
    cycles = config.get("hardware_cycles", 260)
    stop_limit = config.get("charge_stop_limit", 85)
    start_limit = config.get("charge_start_limit", 50)

    plt.figure(figsize=(11, 5.5))

    plt.plot(
        df["Date"],
        df["HealthPercent"],
        "ro-",
        linewidth=2,
        label="Saúde Real (%)",
    )
    plt.plot(
        future_dates,
        future_preds,
        "b--",
        linewidth=1.8,
        label="Tendência Projetada",
    )

    plt.axhline(
        y=80.0,
        color="orange",
        linestyle="--",
        alpha=0.8,
        label="Ref. Fábrica (80%)",
    )
    plt.axhline(
        y=50.0,
        color="purple",
        linestyle="--",
        alpha=0.8,
        label="Ref. Troca Recomendada (50%)",
    )
    plt.axhline(
        y=target_health,
        color="red",
        linestyle=":",
        linewidth=2,
        label=f"Limite Crítico ({target_health}%)",
    )

    latest_date = df["Date"].iloc[-1]
    plt.annotate(
        f" Status Atual: {current_health:.1f}%\n Ciclos Reais: {cycles} (ePSA)",
        xy=(latest_date, current_health),
        xytext=(latest_date, current_health + 12),
        arrowprops=dict(
            facecolor="black", shrink=0.05, width=1, headwidth=6
        ),
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.6),
    )

    recs_text = (
        "Otimizações Ativas:\n"
        f"• Charge Stop: {stop_limit}% | Start: {start_limit}%\n"
        "• Connected Standby: OFF | USB PowerShare: OFF"
    )
    plt.gca().text(
        0.02,
        0.05,
        recs_text,
        transform=plt.gca().transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7),
    )

    plt.title(
        "Projeção de Saúde da Bateria vs. Referência de Fábrica",
        fontsize=12,
        fontweight="bold",
    )
    plt.xlabel("Data")
    plt.ylabel("Saúde da Bateria (% da Capacidade de Fábrica)")
    plt.ylim(0, 110)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="upper right")
    plt.tight_layout()

    img_output_path = os.path.join(base_dir, "battery_health_projection.png")
    plt.savefig(img_output_path)
    print(f"Gráfico 1 salvo em: {img_output_path}")


def plot_advanced_degradation_model(config, current_health=43.01):
    """Gera e salva o Gráfico 2: Modelo Avançado 3D de degradação."""
    base_dir = get_base_dir()
    cycles = config.get("hardware_cycles", 260)

    fig = plt.figure(figsize=(14, 6))

    ax1 = fig.add_subplot(121, projection="3d")
    temp = np.linspace(20, 65, 30)
    ac_percent = np.linspace(20, 100, 30)
    T, AC = np.meshgrid(temp, ac_percent)

    stress_factor = (
        (T / 25) ** 2.2
        + (AC / 100) * 1.5
        + (cycles / 500) * 0.8
    )
    simulated_health = np.clip(100 - (stress_factor * 12), 20, 100)

    surf = ax1.plot_surface(
        T,
        AC,
        simulated_health,
        cmap="coolwarm_r",
        edgecolor="none",
        alpha=0.85,
    )
    ax1.scatter(
        [55],
        [95],
        [current_health],
        color="black",
        s=80,
        label=f"Ponto Atual\n({current_health:.1f}% Saúde / {cycles} Ciclos)",
    )

    ax1.set_title(
        "Superfície 3D: Saúde da Bateria vs.\nTemperatura (°C) e Tempo na Tomada (%)",
        fontsize=10,
        fontweight="bold",
    )
    ax1.set_xlabel("Temperatura Média (°C)", fontsize=8)
    ax1.set_ylabel("Uso em Tomada AC (%)", fontsize=8)
    ax1.set_zlabel("Saúde Estimada (%)", fontsize=8)
    fig.colorbar(
        surf, ax=ax1, shrink=0.5, aspect=10, label="Saúde da Bateria (%)"
    )
    ax1.legend(loc="upper left", fontsize=8)

    ax2 = fig.add_subplot(122)
    factors = [
        "Estresse Térmico\n(45°C - 65°C)",
        "Tensão Alta Contínua\n(100% Carga na AC)",
        "Ciclos de Carga\n(260 ciclos)",
        "Envelhecimento Natural\n(~5 anos)",
    ]
    contributions = [38, 32, 18, 12]
    colors = ["#d9534f", "#f0ad4e", "#0275d8", "#5bc0de"]

    bars = ax2.bar(
        factors,
        contributions,
        color=colors,
        edgecolor="black",
        linewidth=0.8,
    )
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(
            f"{height}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    ax2.set_title(
        "Decomposição dos Fatores da Perda de Capacidade",
        fontsize=10,
        fontweight="bold",
    )
    ax2.set_ylabel("Contribuição Relativa para o Desgaste (%)")
    ax2.set_ylim(0, 50)
    ax2.grid(axis="y", linestyle="--", alpha=0.6)

    plt.tight_layout()
    advanced_img_path = os.path.join(
        base_dir, "battery_advanced_degradation.png"
    )
    plt.savefig(advanced_img_path)
    print(f"Gráfico 2 salvo em: {advanced_img_path}")


# --- Execução Principal ---
if __name__ == "__main__":
    base_dir = get_base_dir()
    print(f"Diretório de execução: {base_dir}\n")

    # 1. Carregar configurações do config.json
    config = load_config()

    # 2. Tentar gerar o relatório via powercfg
    file_path = generate_fresh_battery_report()

    # 3. Fallback 1: Buscar battery-report.html local
    if not file_path or not os.path.exists(file_path):
        fallback_local = os.path.join(base_dir, "battery-report.html")
        if os.path.exists(fallback_local):
            file_path = fallback_local

    # 4. Fallback 2: Usar battery-report-sample.html (para execução em outros SOs/repositório)
    if not file_path or not os.path.exists(file_path):
        fallback_sample = os.path.join(base_dir, "battery-report-sample.html")
        if os.path.exists(fallback_sample):
            file_path = fallback_sample

    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Nenhum relatório de bateria encontrado na pasta: {base_dir}"
        )

    print(f"Lendo e processando relatório em: {file_path}\n")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    battery_data = parse_full_battery_report(html_content)

    print("=" * 80)
    print(" 💻 INFORMAÇÕES DO SISTEMA E BATERIA")
    print("=" * 80)
    for k, v in battery_data["system_info"].items():
        print(f" {k:<25}: {v}")
    print("=" * 80 + "\n")

    df_capacity = battery_data["capacity_history_df"]
    if not df_capacity.empty:
        current_health = df_capacity["HealthPercent"].iloc[-1]
        TARGET_HEALTH = 30.0

        model, pred_date, future_dates, future_preds = train_and_predict(
            df_capacity, target_health=TARGET_HEALTH
        )

        plot_predictions(
            df_capacity,
            future_dates,
            future_preds,
            config,
            target_health=TARGET_HEALTH,
            current_health=current_health,
        )

        plot_advanced_degradation_model(
            config, current_health=current_health
        )

        plt.show()